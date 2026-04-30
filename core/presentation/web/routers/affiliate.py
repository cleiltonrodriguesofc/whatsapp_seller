"""
affiliate offers router.
manages configuration for automated affiliate status posting
and provides manual dispatch trigger.
"""

import asyncio
import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from core.infrastructure.database.models import InstanceModel
from core.infrastructure.database.session import get_db
from core.presentation.web.dependencies import login_required, templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


@router.get("", response_class=HTMLResponse)
async def affiliate_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    instance = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == user.id)
        .first()
    )

    # read current config from env (or sensible defaults)
    config = {
        "ml_token_configured": bool(os.environ.get("ML_ACCESS_TOKEN")),
        "min_discount": int(os.environ.get("MIN_DISCOUNT_PERCENT", "20")),
        "max_offers": int(os.environ.get("MAX_OFFERS_PER_RUN", "3")),
        "dispatch_hours": os.environ.get("STATUS_DISPATCH_HOURS", "9,12,18"),
    }

    return templates.TemplateResponse(
        request=request,
        name="affiliate_dashboard.html",
        context={
            "request": request,
            "user": user,
            "has_instance": instance is not None,
            "config": config,
        },
    )


@router.post("/dispatch")
async def dispatch_affiliate_offers(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """manually triggers affiliate status dispatch."""
    from core.application.use_cases.dispatch_status_offers import DispatchStatusOffers
    from core.infrastructure.gateways.mercadolivre_gateway import MercadoLivreGateway
    from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService

    ml_token = os.environ.get("ML_ACCESS_TOKEN")
    if not ml_token:
        return JSONResponse(
            {"success": False, "error": "ML_ACCESS_TOKEN não configurado"},
            status_code=400,
        )

    instance = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == user.id)
        .first()
    )
    if not instance:
        return JSONResponse(
            {"success": False, "error": "Nenhuma instância WhatsApp conectada"},
            status_code=400,
        )

    gateway = MercadoLivreGateway(access_token=ml_token)
    whatsapp = EvolutionWhatsAppService(
        instance=instance.name,
        apikey=instance.apikey,
    )

    # try to load ai service for copy generation
    ai_service = None
    try:
        from core.infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
    except Exception:
        logger.info("[affiliate] ai service not available, using fallback copy")

    min_discount = float(os.environ.get("MIN_DISCOUNT_PERCENT", "20"))
    max_offers = int(os.environ.get("MAX_OFFERS_PER_RUN", "3"))

    use_case = DispatchStatusOffers(
        gateway=gateway,
        whatsapp=whatsapp,
        ai_service=ai_service,
        min_discount=min_discount,
    )

    async def run():
        try:
            await use_case.execute(max_offers=max_offers)
        except Exception as e:
            logger.error("[affiliate] dispatch error: %s", e)

    asyncio.create_task(run())
    return JSONResponse({"success": True, "message": "Disparo de ofertas iniciado em segundo plano"})
