"""
affiliate offers router.
manages configuration for automated magalu affiliate status posting
and provides manual dispatch trigger.
"""

import asyncio
import base64
import logging

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from core.infrastructure.database.models import InstanceModel, AffiliateConfigModel, AffiliateLogModel
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
            "require_approval": config_model.require_approval or False,
            "preferred_brands": config_model.preferred_brands or "",
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
            "require_approval": False,
            "preferred_brands": "",
        }

    # build category options for the template
    available_categories = MagaluGateway.get_available_categories()

    has_avatar = bool(config_model and config_model.owner_avatar_b64)

    return templates.TemplateResponse(
        request=request,
        name="affiliate_dashboard.html",
        context={
            "request": request,
            "user": user,
            "has_instance": instance is not None,
            "config": config,
            "available_categories": available_categories,
            "has_avatar": has_avatar,
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
    require_approval: bool = False
    preferred_brands: str = ""


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
    config.require_approval = data.require_approval
    config.preferred_brands = data.preferred_brands

    db.commit()
    return JSONResponse({"success": True, "message": "Configurações salvas com sucesso!"})


# ── avatar upload ────────────────────────────────────────────────

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """uploads the store owner avatar and persists it as base64 in the database."""
    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    if not config:
        config = AffiliateConfigModel(user_id=user.id)
        db.add(config)

    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:  # 2mb limit
        return JSONResponse({"success": False, "error": "Imagem muito grande (max 2MB)"}, status_code=400)

    config.owner_avatar_b64 = base64.b64encode(contents).decode("utf-8")
    db.commit()
    return JSONResponse({"success": True, "message": "Avatar salvo com sucesso!"})


@router.delete("/avatar")
async def delete_avatar(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """removes the stored avatar."""
    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()
    if config:
        config.owner_avatar_b64 = None
        db.commit()
    return JSONResponse({"success": True, "message": "Avatar removido."})


@router.get("/logs")
async def get_affiliate_logs(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """returns the last 20 affiliate logs for the user."""
    logs = (
        db.query(AffiliateLogModel)
        .filter(AffiliateLogModel.user_id == user.id)
        .order_by(AffiliateLogModel.created_at.desc())
        .limit(20)
        .all()
    )
    return [{
        "id": l.id,
        "product_title": l.product_title,
        "image_url": l.image_url,
        "status": l.status,
        "price": l.price,
        "discount_percent": l.discount_percent,
        "created_at": l.created_at.strftime("%H:%M:%S"),
        "error": l.error_message
    } for l in logs]


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
                preferred_brands=config.preferred_brands or "",
            )

            if not offers:
                logger.info("[affiliate] no qualifying offers found")
                # Log that no offers were found
                with next(get_db()) as db_session:
                    db_session.add(AffiliateLogModel(
                        user_id=user.id,
                        product_title="Nenhuma oferta encontrada no momento",
                        original_url="",
                        status="info"
                    ))
                    db_session.commit()
                return

            # Log start of search
            with next(get_db()) as db_session:
                db_session.add(AffiliateLogModel(
                    user_id=user.id,
                    product_title=f"Buscando ofertas em: {', '.join(categories)}",
                    original_url="",
                    status="info"
                ))
                db_session.commit()

            with next(get_db()) as db_session:
                from datetime import timedelta
                
                recent_logs = db_session.query(AffiliateLogModel.product_title).filter(
                    AffiliateLogModel.user_id == user.id,
                    AffiliateLogModel.created_at >= datetime.utcnow() - timedelta(days=7)
                ).all()
                recent_titles = {log[0] for log in recent_logs}

                new_offers = []
                for offer in offers:
                    if offer.title not in recent_titles:
                        new_offers.append(offer)
                        recent_titles.add(offer.title)

            if not new_offers:
                logger.info("[affiliate] all fetched offers are duplicates")
                with next(get_db()) as db_session:
                    db_session.add(AffiliateLogModel(
                        user_id=user.id,
                        product_title="Nenhuma oferta nova encontrada no momento",
                        original_url="",
                        status="info"
                    ))
                    db_session.commit()
                return

            for offer in new_offers:
                from core.infrastructure.utils.shortener import get_or_create_shortlink
                
                with next(get_db()) as db_session:
                    short_link_url = get_or_create_shortlink(db_session, offer.affiliate_link, config.storefront_slug)

                    # If manual approval is required, just log it as pending and skip sending
                    if config.require_approval:
                        db_session.add(AffiliateLogModel(
                            user_id=user.id,
                            product_title=offer.title,
                            image_url=offer.image_url,
                            original_url=offer.affiliate_link,
                            short_url=short_link_url,
                            price=offer.price,
                            old_price=offer.old_price,
                            discount_percent=offer.discount_percent,
                            installment_text=offer.installment_text,
                            pix_discount_text=offer.pix_discount_text,
                            status="pending"
                        ))
                        db_session.commit()
                        logger.info("[affiliate] pending offer saved: %s", offer.title[:40])
                
                if config.require_approval:
                    continue

                # Auto dispatch flow
                if ai_service:
                    try:
                        copy = await ai_service.generate_affiliate_copy(
                            title=offer.title,
                            price=offer.price,
                            old_price=offer.old_price,
                            discount=offer.discount_percent,
                            link=short_link_url,
                            installment_text=offer.installment_text,
                            pix_discount_text=offer.pix_discount_text,
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
                        + (f"💳 {offer.installment_text}\n" if offer.installment_text else "")
                        + (f"💸 {offer.pix_discount_text}\n\n" if offer.pix_discount_text else "\n")
                        + f"👉 {short_link_url}"
                    )

                # post to whatsapp status
                try:
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
                        owner_avatar_b64=config.owner_avatar_b64 or "",
                    )
                    
                    if card_bytes:
                        b64_img = base64.b64encode(card_bytes).decode("utf-8")  # noqa: F841
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
                
                # Save log to DB
                with next(get_db()) as db_session:
                    db_session.add(AffiliateLogModel(
                        user_id=user.id,
                        product_title=offer.title,
                        image_url=offer.image_url,
                        original_url=offer.affiliate_link,
                        short_url=short_link_url,
                        price=offer.price,
                        discount_percent=offer.discount_percent,
                        status="sent"
                    ))
                    db_session.commit()
                
                await asyncio.sleep(5)  # delay between posts

            logger.info("[affiliate] dispatch complete: %d offers processed", len(offers))

        except Exception as e:
            logger.error("[affiliate] dispatch error: %s", e)
            with next(get_db()) as db_session:
                db_session.add(AffiliateLogModel(
                    user_id=user.id,
                    product_title="Erro no processo de busca/postagem",
                    original_url="",
                    status="failed",
                    error_message=str(e)
                ))
                db_session.commit()

    asyncio.create_task(run())
    return JSONResponse({"success": True, "message": "Disparo de ofertas iniciado em segundo plano"})


@router.get("/offers/{log_id}/preview")
async def preview_affiliate_offer(
    log_id: int,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """Generates and returns the promo card and AI copy for preview."""
    from core.infrastructure.image.promo_card_generator import generate_promo_card

    log = db.query(AffiliateLogModel).filter(
        AffiliateLogModel.id == log_id,
        AffiliateLogModel.user_id == user.id,
        AffiliateLogModel.status == "pending"
    ).first()
    
    if not log:
        return JSONResponse({"success": False, "error": "Oferta não encontrada ou não pendente."}, status_code=404)

    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    ai_service = None
    try:
        from core.infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
    except Exception:
        pass

    try:
        copy = None
        if ai_service:
            try:
                copy = await ai_service.generate_affiliate_copy(
                    title=log.product_title,
                    price=log.price,
                    old_price=log.old_price,
                    discount=log.discount_percent,
                    link=log.short_url,
                    installment_text=log.installment_text or "",
                    pix_discount_text=log.pix_discount_text or "",
                )
            except Exception:
                pass

        if not copy:
            old_str = f"~~R$ {log.old_price:,.2f}~~ ".replace(",", "X").replace(".", ",").replace("X", ".") if log.old_price else ""
            copy = (
                f"🔥 *{log.product_title}*\n\n"
                f"{old_str}"
                f"💰 *R$ {log.price:,.2f}*\n".replace(",", "X").replace(".", ",").replace("X", ".")
                + (f"💳 {log.installment_text}\n" if log.installment_text else "")
                + (f"💸 {log.pix_discount_text}\n\n" if log.pix_discount_text else "\n")
                + f"👉 {log.short_url}"
            )

        card_bytes = await generate_promo_card(
            title=log.product_title,
            price=log.price,
            old_price=log.old_price,
            discount_percent=log.discount_percent,
            image_url=log.image_url,
            storefront_name=config.storefront_slug if config else "",
            store_type=config.store_type if config else "magalu",
            theme_color=config.theme_color if config else "#0088ff",
            tagline=config.tagline if config else "tem na minha loja",
            installment_text=log.installment_text or "",
            pix_discount_text=log.pix_discount_text or "",
            owner_avatar_b64=config.owner_avatar_b64 if config else "",
        )

        b64_img = ""
        if card_bytes:
            b64_img = base64.b64encode(card_bytes).decode("utf-8")

        return JSONResponse({
            "success": True,
            "copy": copy,
            "image_b64": b64_img
        })

    except Exception as e:
        logger.error(f"[affiliate] Preview error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/offers/{log_id}/approve")
async def approve_affiliate_offer(
    log_id: int,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """Approves a pending offer and sends it to WhatsApp."""
    from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
    
    log = db.query(AffiliateLogModel).filter(
        AffiliateLogModel.id == log_id,
        AffiliateLogModel.user_id == user.id,
        AffiliateLogModel.status == "pending"
    ).first()
    
    if not log:
        return JSONResponse({"success": False, "error": "Oferta não encontrada ou não está pendente."}, status_code=404)
        
    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()
    
    instance = db.query(InstanceModel).filter(InstanceModel.user_id == user.id).first()
    if not instance:
         return JSONResponse({"success": False, "error": "Nenhuma instância WhatsApp conectada."}, status_code=400)
         
    whatsapp = EvolutionWhatsAppService(instance=instance.name, apikey=instance.apikey)
    
    ai_service = None
    try:
        from core.infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
    except Exception:
        pass

    async def _send_approved_offer():
        try:
            copy = None
            if ai_service:
                try:
                    copy = await ai_service.generate_affiliate_copy(
                        title=log.product_title,
                        price=log.price,
                        old_price=log.old_price,
                        discount=log.discount_percent,
                        link=log.short_url,
                        installment_text=log.installment_text or "",
                        pix_discount_text=log.pix_discount_text or "",
                    )
                except Exception:
                    pass

            if not copy:
                old_str = f"~~R$ {log.old_price:,.2f}~~ ".replace(",", "X").replace(".", ",").replace("X", ".") if log.old_price else ""
                copy = (
                    f"🔥 *{log.product_title}*\n\n"
                    f"{old_str}"
                    f"💰 *R$ {log.price:,.2f}*\n".replace(",", "X").replace(".", ",").replace("X", ".")
                    + (f"💳 {log.installment_text}\n" if log.installment_text else "")
                    + (f"💸 {log.pix_discount_text}\n\n" if log.pix_discount_text else "\n")
                    + f"👉 {log.short_url}"
                )

            card_bytes = await generate_promo_card(
                title=log.product_title,
                price=log.price,
                old_price=log.old_price,
                discount_percent=log.discount_percent,
                image_url=log.image_url,
                storefront_name=config.storefront_slug if config else "",
                store_type=config.store_type if config else "magalu",
                theme_color=config.theme_color if config else "#0088ff",
                tagline=config.tagline if config else "tem na minha loja",
                installment_text=log.installment_text or "",
                pix_discount_text=log.pix_discount_text or "",
                owner_avatar_b64=config.owner_avatar_b64 if config else "",
            )
            
            if card_bytes:
                b64_img = base64.b64encode(card_bytes).decode("utf-8")
                await whatsapp.send_status(content=b64_img, type="image", caption=copy)
            else:
                await whatsapp.send_status(content=copy)
                
            with next(get_db()) as db_session:
                db_log = db_session.query(AffiliateLogModel).get(log.id)
                db_log.status = "sent"
                db_session.commit()
                
        except Exception as e:
            logger.error(f"[affiliate] Failed to send approved offer: {e}")
            with next(get_db()) as db_session:
                db_log = db_session.query(AffiliateLogModel).get(log.id)
                db_log.status = "failed"
                db_log.error_message = str(e)
                db_session.commit()

    asyncio.create_task(_send_approved_offer())
    
    # Mark as processing immediately
    log.status = "processing"
    db.commit()
    
    return JSONResponse({"success": True, "message": "Oferta aprovada e enviada para processamento."})


@router.post("/offers/{log_id}/reject")
async def reject_affiliate_offer(
    log_id: int,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    log = db.query(AffiliateLogModel).filter(
        AffiliateLogModel.id == log_id,
        AffiliateLogModel.user_id == user.id,
        AffiliateLogModel.status == "pending"
    ).first()
    
    if not log:
        return JSONResponse({"success": False, "error": "Oferta não encontrada ou não está pendente."}, status_code=404)
        
    log.status = "rejected"
    db.commit()
    return JSONResponse({"success": True, "message": "Oferta rejeitada."})
