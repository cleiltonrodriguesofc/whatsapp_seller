from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import os
import mercadopago
import logging
from datetime import datetime

from core.infrastructure.database.models import (
    UserModel,
    SubscriptionModel,
    PlanModel,
    ReferralConversionModel,
)
from core.infrastructure.database.session import get_db
from core.presentation.web.dependencies import templates, login_required

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")


@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request, db: Session = Depends(get_db)):
    plans = db.query(PlanModel).all()
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"plans": plans, "scroll_to": "pricing"},
    )


@router.post("/checkout/create-session")
async def create_checkout_session(
    plan_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    if not MP_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Mercado Pago token not configured")

    plan = db.query(PlanModel).filter(PlanModel.name == plan_name).first()
    if not plan or not plan.mp_plan_id:
        raise HTTPException(
            status_code=404, detail="Plan not found or not configured for Mercado Pago"
        )

    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

    # Preapproval (subscription) creation
    # For simplicity in this MVP, we use the plan's mp_plan_id
    preapproval_data = {
        "preapproval_plan_id": plan.mp_plan_id,
        "payer_email": current_user.email,
        "back_url": f"{os.environ.get('BASE_URL', 'http://localhost:8000')}/checkout/success",
        "external_reference": str(current_user.id),
        "reason": f"WhatSeller Pro - Plano {plan.display_name}",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": plan.price_brl,
            "currency_id": "BRL",
        },
        "status": "pending",
    }

    result = sdk.preapproval().create(preapproval_data)

    if result["status"] >= 400:
        logger.error(f"MP Error: {result['response']}")
        raise HTTPException(status_code=400, detail="Error creating checkout session")

    init_point = result["response"]["init_point"]
    return RedirectResponse(url=init_point, status_code=303)


@router.get("/checkout/success")
async def checkout_success(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="checkout_status.html",
        context={
            "status": "success",
            "message": "Sua assinatura está sendo processada!",
        },
    )


@router.get("/checkout/cancel")
async def checkout_cancel(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="checkout_status.html",
        context={"status": "cancel", "message": "O pagamento foi cancelado."},
    )


@router.post("/webhooks/mercadopago")
async def mp_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    # We check for preapproval (subscription) updates
    if (
        data.get("action") == "created"
        or data.get("type") == "subscription_preapproval"
    ):
        resource_id = data.get("data", {}).get("id") or data.get("id")
        if not resource_id:
            return {"status": "ok"}

        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        result = sdk.preapproval().get(resource_id)
        preapproval = result["response"]

        user_id = int(preapproval.get("external_reference"))
        status = preapproval.get("status")  # "authorized", "paused", "cancelled"

        subscription = (
            db.query(SubscriptionModel)
            .filter(SubscriptionModel.user_id == user_id)
            .first()
        )
        if subscription:
            if status == "authorized":
                subscription.status = "active"
                subscription.mp_preapproval_id = resource_id
                # Logic for referral reward on first payment
                handle_referral_reward(user_id, db)
            elif status == "cancelled":
                subscription.status = "canceled"
            elif status == "paused":
                subscription.status = "past_due"

            db.commit()

    return {"status": "ok"}


def handle_referral_reward(user_id: int, db: Session):
    # Check if this user was referred
    conversion = (
        db.query(ReferralConversionModel)
        .filter(
            ReferralConversionModel.referred_id == user_id,
            ReferralConversionModel.status == "pending",
        )
        .first()
    )

    if conversion:
        subscription = (
            db.query(SubscriptionModel)
            .filter(SubscriptionModel.user_id == user_id)
            .first()
        )
        if subscription and subscription.plan:
            reward = round(subscription.plan.price_brl * 0.30, 2)
            conversion.status = "rewarded"
            conversion.reward_brl = reward
            conversion.rewarded_at = datetime.utcnow()

            # Add to referrer balance
            referrer = (
                db.query(UserModel)
                .filter(UserModel.id == conversion.referrer_id)
                .first()
            )
            if referrer:
                referrer.referral_balance += reward

            db.commit()


@router.get("/dashboard/billing", response_class=HTMLResponse)
async def billing_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    subscription = (
        db.query(SubscriptionModel)
        .filter(SubscriptionModel.user_id == current_user.id)
        .first()
    )
    plans = db.query(PlanModel).all()
    return templates.TemplateResponse(
        request=request,
        name="billing_dashboard.html",
        context={
            "user": current_user,
            "subscription": subscription,
            "plans": plans,
            "title": "Faturamento",
        },
    )
