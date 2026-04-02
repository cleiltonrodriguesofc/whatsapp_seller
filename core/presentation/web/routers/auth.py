"""
Authentication routes: login, register, logout.
"""

import logging
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from datetime import datetime, timedelta
import string
import random

from core.infrastructure.database.models import (
    InstanceModel, 
    UserModel, 
    SubscriptionModel, 
    PlanModel, 
    ReferralCodeModel, 
    ReferralConversionModel
)
from core.infrastructure.database.session import get_db
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.presentation.web.dependencies import auth_service, templates

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"title": "Login"})


@router.post("/login")
@limiter.limit("10/minute")
async def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.email == username).first()
    if not user or not auth_service.verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid email or password", "title": "Login"},
        )

    access_token = auth_service.create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    is_prod = os.environ.get("RENDER") == "true"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={"title": "Register"})


@router.post("/register")
@limiter.limit("5/minute")
async def register_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    business_name: str = Form(...),
    terms_accepted: str = Form(...),
    db: Session = Depends(get_db),
):
    if terms_accepted != "on":
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Você precisa aceitar os Termos de Uso.", "title": "Register"},
        )

    existing_user = db.query(UserModel).filter(UserModel.email == email).first()
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Email already registered", "title": "Register"},
        )

    new_user = UserModel(
        email=email, 
        hashed_password=auth_service.hash_password(password),
        agreed_to_terms_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 1. generate referral code for the new user
    def generate_code(length=8):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    unique_code = generate_code()
    while db.query(ReferralCodeModel).filter(ReferralCodeModel.code == unique_code).first():
        unique_code = generate_code()
        
    user_ref_code = ReferralCodeModel(user_id=new_user.id, code=unique_code)
    db.add(user_ref_code)
    db.commit()
    db.refresh(user_ref_code)
    
    new_user.referral_code_id = user_ref_code.id
    db.commit()

    # 2. handle referral from another user
    ref_code = request.query_params.get("ref")
    if ref_code:
        referrer_code_obj = db.query(ReferralCodeModel).filter(ReferralCodeModel.code == ref_code).first()
        if referrer_code_obj and referrer_code_obj.user_id != new_user.id:
            conversion = ReferralConversionModel(
                referrer_id=referrer_code_obj.user_id,
                referred_id=new_user.id,
                status="pending"
            )
            db.add(conversion)
            db.commit()

    # 3. create 3-day trial subscription
    # first, ensure a 'starter' plan exists (or use a default)
    starter_plan = db.query(PlanModel).filter(PlanModel.name == "starter").first()
    if not starter_plan:
        # fallback/auto-create if not exists for trial
        starter_plan = PlanModel(
            name="starter",
            display_name="Starter",
            price_brl=97.00,
            max_instances=1,
            has_ai=False
        )
        db.add(starter_plan)
        db.commit()
        db.refresh(starter_plan)

    trial_subscription = SubscriptionModel(
        user_id=new_user.id,
        plan_id=starter_plan.id,
        status="trialing",
        trial_ends_at=datetime.utcnow() + timedelta(days=3)
    )
    db.add(trial_subscription)
    db.commit()

    # provision whitatsapp instance
    try:
        instance_name = business_name.lower().replace(" ", "_") + "_" + str(new_user.id)
        whatsapp_service = EvolutionWhatsAppService()
        instance_data = await whatsapp_service.create_instance(instance_name, display_name=business_name)

        if instance_data and isinstance(instance_data, dict):
            hash_data = instance_data.get("hash")
            if isinstance(hash_data, dict):
                apikey = hash_data.get("apikey")
            elif isinstance(hash_data, str):
                apikey = hash_data
            else:
                apikey = instance_data.get("apikey")

            new_instance = InstanceModel(
                user_id=new_user.id,
                name=instance_name,
                display_name=business_name,
                apikey=apikey,
            )
            db.add(new_instance)
            db.commit()
        else:
            logger.warning(
                "evolution api returned non-dict response for %s: %s",
                instance_name,
                type(instance_data),
            )
    except Exception as e:
        logger.error("post-registration instance provisioning failed: %s", e, exc_info=True)

    access_token = auth_service.create_access_token(data={"sub": new_user.email})
    response = RedirectResponse(url="/whatsapp/connect", status_code=HTTP_303_SEE_OTHER)
    is_prod = os.environ.get("RENDER") == "true"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response
