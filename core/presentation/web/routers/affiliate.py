"""
affiliate offers router.
manages configuration for automated magalu affiliate status posting
and provides manual dispatch trigger.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from core.infrastructure.database.models import InstanceModel, AffiliateConfigModel
from core.infrastructure.database.session import get_db
from core.infrastructure.gateways.magalu_gateway import MagaluGateway, CATEGORY_MAP
from core.infrastructure.image.promo_card_generator import generate_promo_card
from pydantic import BaseModel
from core.presentation.web.dependencies import login_required, templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


# ── dashboard ────────────────────────────────────────────────────

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

    config_model = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    if config_model:
        active_cats = [c.strip() for c in (config_model.categories or "").split(",") if c.strip()]
        config = {
            "configured": bool(config_model.storefront_slug),
            "storefront_slug": config_model.storefront_slug or "",
            "categories": active_cats,
            "min_discount": config_model.min_discount_percent,
            "max_offers": config_model.max_offers_per_run,
            "dispatch_hours": config_model.dispatch_hours,
            "store_type": config_model.store_type or "magalu",
            "theme_color": config_model.theme_color or "#0088ff",
            "tagline": config_model.tagline or "tem na minha loja",
        }
    else:
        config = {
            "configured": False,
            "storefront_slug": "",
            "categories": ["notebook", "celular"],
            "min_discount": 10.0,
            "max_offers": 5,
            "dispatch_hours": "9,12,18",
            "store_type": "magalu",
            "theme_color": "#0088ff",
            "tagline": "tem na minha loja",
        }

    # build category options for the template
    available_categories = MagaluGateway.get_available_categories()

    return templates.TemplateResponse(
        request=request,
        name="affiliate_dashboard.html",
        context={
            "request": request,
            "user": user,
            "has_instance": instance is not None,
            "config": config,
            "available_categories": available_categories,
        },
    )


# ── save config ──────────────────────────────────────────────────

class AffiliateConfigSchema(BaseModel):
    storefront_slug: str
    categories: list[str]
    min_discount: float
    max_offers: int
    dispatch_hours: str
    store_type: str = "magalu"
    theme_color: str = "#0088ff"
    tagline: str = "tem na minha loja"


@router.post("/config")
async def save_affiliate_config(
    data: AffiliateConfigSchema,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    if not config:
        config = AffiliateConfigModel(user_id=user.id)
        db.add(config)

    config.storefront_slug = data.storefront_slug.strip().lower()
    config.categories = ",".join(data.categories)
    config.min_discount_percent = data.min_discount
    config.max_offers_per_run = data.max_offers
    config.dispatch_hours = data.dispatch_hours
    config.store_type = data.store_type
    config.theme_color = data.theme_color
    config.tagline = data.tagline

    db.commit()
    return JSONResponse({"success": True, "message": "Configurações salvas com sucesso!"})


# ── manual dispatch ──────────────────────────────────────────────

@router.post("/dispatch")
async def dispatch_affiliate_offers(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """manually triggers affiliate status dispatch."""
    from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService

    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    if not config or not config.storefront_slug:
        return JSONResponse(
            {"success": False, "error": "Configure seu slug da loja Magalu primeiro"},
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

    categories = [c.strip() for c in (config.categories or "notebook,celular").split(",") if c.strip()]

    gateway = MagaluGateway(storefront_slug=config.storefront_slug)
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

    async def run():
        try:
            offers = await gateway.get_offers(
                categories=categories,
                min_discount_percent=config.min_discount_percent,
                max_offers=config.max_offers_per_run,
            )

            if not offers:
                logger.info("[affiliate] no qualifying offers found")
                return

            for offer in offers:
                # build status message
                from core.infrastructure.utils.shortener import get_or_create_shortlink
                short_link_url = get_or_create_shortlink(db, offer.affiliate_link, config.storefront_slug)

                if ai_service:
                    try:
                        copy = await ai_service.generate_affiliate_copy(
                            title=offer.title,
                            price=offer.price,
                            old_price=offer.old_price,
                            discount=offer.discount_percent,
                            link=short_link_url,
                        )
                    except Exception:
                        copy = None
                else:
                    copy = None

                if not copy:
                    copy = (
                        f"🔥 *{offer.title}*\n\n"
                        f"{'~~R$ ' + f'{offer.old_price:,.2f}'.replace(',','X').replace('.',',').replace('X','.') + '~~  ' if offer.old_price else ''}"
                        f"💰 *R$ {offer.price:,.2f}*\n".replace(",", "X").replace(".", ",").replace("X", ".")
                        + f"📉 *{offer.discount_percent:.0f}% OFF*\n\n"
                        f"👉 {short_link_url}"
                    )

                # post to whatsapp status
                try:
                    import base64
                    card_bytes = await generate_promo_card(
                        title=offer.title,
                        price=offer.price,
                        old_price=offer.old_price,
                        discount_percent=offer.discount_percent,
                        image_url=offer.image_url,
                        storefront_name=config.storefront_slug,
                        store_type=config.store_type or "magalu",
                        theme_color=config.theme_color or "#0088ff",
                        tagline=config.tagline or "tem na minha loja",
                        installment_text=offer.installment_text,
                        pix_discount_text=offer.pix_discount_text,
                    )
                    
                    if card_bytes:
                        b64_img = base64.b64encode(card_bytes).decode("utf-8")
                        await whatsapp.send_status(
                            content=b64_img,
                            type="image",
                            caption=copy
                        )
                    else:
                        raise Exception("failed to generate card bytes")
                except Exception as e:
                    logger.error("[affiliate] error generating card: %s", e)
                    # fallback to text only
                    await whatsapp.send_status(content=copy)

                logger.info("[affiliate] posted offer: %s (%.0f%% off)", offer.title[:40], offer.discount_percent)
                await asyncio.sleep(5)  # delay between posts

            logger.info("[affiliate] dispatch complete: %d offers posted", len(offers))

        except Exception as e:
            logger.error("[affiliate] dispatch error: %s", e)

    asyncio.create_task(run())
    return JSONResponse({"success": True, "message": "Disparo de ofertas iniciado em segundo plano"})
