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
        ml_cats = [c.strip() for c in (config_model.ml_categories or "").split(",") if c.strip()]
        import json
        try:
            group_jids = json.loads(config_model.group_jids or "[]") if config_model.group_jids else []
        except Exception:
            group_jids = []
        config = {
            "configured": bool(config_model.storefront_slug) or bool(config_model.ml_profile_slug),
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
            # ml fields
            "ml_profile_slug": config_model.ml_profile_slug or "",
            "ml_enabled": config_model.ml_enabled or False,
            "ml_categories": ml_cats,
            # group fields
            "group_enabled": config_model.group_enabled or False,
            "group_jids": group_jids,
            "group_dispatch_hours": config_model.group_dispatch_hours or "9,12,15,18,21",
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
            # ml fields
            "ml_profile_slug": "",
            "ml_enabled": False,
            "ml_categories": ["notebook", "celular"],
            # group fields
            "group_enabled": False,
            "group_jids": [],
            "group_dispatch_hours": "9,12,15,18,21",
        }

    # build category options for the template
    available_categories = MagaluGateway.get_available_categories()
    from core.infrastructure.gateways.mercadolivre_gateway import MercadoLivreGateway
    available_ml_categories = MercadoLivreGateway.get_available_categories()

    has_avatar = bool(config_model and config_model.owner_avatar_b64)

    # fetch available groups from the connected instance
    available_groups = []
    if instance:
        try:
            from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
            ws = EvolutionWhatsAppService(instance=instance.name, apikey=instance.apikey)
            raw_groups = await ws.get_groups()
            if isinstance(raw_groups, list):
                for g in raw_groups:
                    gid = g.get("id") or g.get("remoteJid") or ""
                    if gid:
                        available_groups.append({
                            "id": gid,
                            "name": g.get("subject") or g.get("name") or gid.split("@")[0],
                        })
        except Exception as e:
            logger.warning("could not fetch groups for affiliate dashboard: %s", e)

    return templates.TemplateResponse(
        request=request,
        name="affiliate_dashboard.html",
        context={
            "request": request,
            "user": user,
            "has_instance": instance is not None,
            "config": config,
            "available_categories": available_categories,
            "available_ml_categories": available_ml_categories,
            "has_avatar": has_avatar,
            "available_groups": available_groups,
        },
    )


# ── save config ──────────────────────────────────────────────────

class AffiliateConfigSchema(BaseModel):
    storefront_slug: str = ""
    categories: list[str] = []
    min_discount: float = 10.0
    max_offers: int = 5
    dispatch_hours: str = "9,12,18"
    store_type: str = "magalu"
    theme_color: str = "#0088ff"
    tagline: str = "tem na minha loja"
    require_approval: bool = False
    preferred_brands: str = ""
    # ml affiliate
    ml_profile_slug: str = ""
    ml_enabled: bool = False
    ml_categories: list[str] = []
    # group broadcast
    group_enabled: bool = False
    group_jids: list[str] = []
    group_dispatch_hours: str = "9,12,15,18,21"


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
    # ml fields
    config.ml_profile_slug = data.ml_profile_slug.strip()
    config.ml_enabled = data.ml_enabled
    config.ml_categories = ",".join(data.ml_categories) if data.ml_categories else "notebook,celular"
    # group fields
    import json
    config.group_enabled = data.group_enabled
    config.group_jids = json.dumps(data.group_jids)
    config.group_dispatch_hours = data.group_dispatch_hours

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


# ── fetch offers (no send) ─────────────────────────────────────────

@router.get("/fetch-offers")
async def fetch_affiliate_offers(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """
    fetches offers from magalu and/or mercado livre WITHOUT sending anything.
    returns the list so the ui can display a picker for the user to choose.
    """
    from core.infrastructure.gateways.mercadolivre_gateway import MercadoLivreGateway

    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    if not config:
        return JSONResponse({"success": False, "error": "Configure o afiliado primeiro."}, status_code=400)

    has_magalu = bool(config.storefront_slug)
    has_ml = bool(config.ml_enabled and config.ml_profile_slug)

    if not has_magalu and not has_ml:
        return JSONResponse(
            {"success": False, "error": "Configure ao menos a loja Magalu ou o perfil Mercado Livre."},
            status_code=400,
        )

    categories = [c.strip() for c in (config.categories or "notebook,celular").split(",") if c.strip()]
    ml_categories = [c.strip() for c in (config.ml_categories or "notebook,celular").split(",") if c.strip()]
    min_discount = config.min_discount_percent or 5.0
    max_offers = config.max_offers_per_run or 5

    all_offers: list[dict] = []

    # ── magalu ───────────────────────────────────────────────────────
    if has_magalu:
        try:
            gw = MagaluGateway(storefront_slug=config.storefront_slug)
            raw = await gw.get_offers(
                categories=categories,
                min_discount_percent=min_discount,
                max_offers=max_offers,
                preferred_brands=config.preferred_brands or "",
            )
            for o in raw:
                all_offers.append({
                    "title": o.title,
                    "price": o.price,
                    "old_price": o.old_price,
                    "discount_percent": o.discount_percent,
                    "image_url": o.image_url,
                    "affiliate_link": o.affiliate_link,
                    "installment_text": o.installment_text,
                    "pix_discount_text": o.pix_discount_text,
                    "source": "magalu",
                })
        except Exception as e:
            logger.error("[fetch-offers] magalu error: %s", e)

    # ── mercado livre ─────────────────────────────────────────────────
    if has_ml:
        try:
            ml_gw = MercadoLivreGateway(profile_slug=config.ml_profile_slug)
            raw_ml = await ml_gw.get_offers(
                categories=ml_categories,
                min_discount_percent=min_discount,
                max_offers=max_offers,
            )
            for o in raw_ml:
                all_offers.append({
                    "title": o.title,
                    "price": o.price,
                    "old_price": o.old_price,
                    "discount_percent": o.discount_percent,
                    "image_url": o.image_url,
                    "affiliate_link": o.affiliate_link,
                    "installment_text": o.installment_text,
                    "pix_discount_text": "",
                    "source": "mercadolivre",
                })
        except Exception as e:
            logger.error("[fetch-offers] ml error: %s", e)

    return JSONResponse({"success": True, "offers": all_offers})


# ── manual dispatch (send selected offers to chosen targets) ─────────

class ManualDispatchSchema(BaseModel):
    offers: list[dict]        # list of offer dicts from /fetch-offers
    targets: list[str]        # e.g. ["status"], ["groups"] or ["status","groups"]


@router.post("/dispatch")
async def dispatch_affiliate_offers(
    data: ManualDispatchSchema,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """manually triggers dispatch for the user-selected offers and targets."""
    from core.presentation.web.scheduler import execute_manual_selected_dispatch

    if not data.offers:
        return JSONResponse({"success": False, "error": "Selecione pelo menos uma oferta."}, status_code=400)
    if not data.targets:
        return JSONResponse({"success": False, "error": "Selecione pelo menos um destino (Status ou Grupos)."}, status_code=400)

    config = db.query(AffiliateConfigModel).filter(
        AffiliateConfigModel.user_id == user.id
    ).first()

    instance = db.query(InstanceModel).filter(
        InstanceModel.user_id == user.id,
        InstanceModel.status == "connected",
    ).first()

    if not instance:
        return JSONResponse({"success": False, "error": "Nenhuma instância WhatsApp conectada."}, status_code=400)

    if "groups" in data.targets:
        import json as _json
        try:
            group_jids = _json.loads(config.group_jids or "[]") if config and config.group_jids else []
        except Exception:
            group_jids = []
        if not group_jids:
            return JSONResponse(
                {"success": False, "error": "Nenhum grupo configurado. Adicione grupos nas configurações."},
                status_code=400,
            )
    else:
        group_jids = []

    config_snapshot = {
        "store_type": config.store_type if config else "magalu",
        "theme_color": config.theme_color if config else "#0088ff",
        "tagline": config.tagline if config else "tem na minha loja",
        "owner_avatar_b64": config.owner_avatar_b64 if config else "",
        "storefront_slug": config.storefront_slug if config else "",
        "group_jids": group_jids,
    }

    import asyncio as _asyncio
    _asyncio.create_task(execute_manual_selected_dispatch(
        user_id=user.id,
        instance_name=instance.name,
        instance_apikey=instance.apikey,
        offers_data=data.offers,
        targets=data.targets,
        config_snapshot=config_snapshot,
    ))

    dest_labels = []
    if "status" in data.targets:
        dest_labels.append("Status")
    if "groups" in data.targets:
        dest_labels.append("Grupos")

    return JSONResponse({
        "success": True,
        "message": f"Disparando {len(data.offers)} oferta(s) para: {' e '.join(dest_labels)}. Aguarde..."
    })




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

    # Extract required values to avoid DetachedInstanceError in async task
    log_id_val = log.id
    log_title = log.product_title
    log_price = log.price
    log_old_price = log.old_price
    log_discount = log.discount_percent
    log_short_url = log.short_url
    log_installment = log.installment_text or ""
    log_pix_discount = log.pix_discount_text or ""
    log_image_url = log.image_url

    storefront_slug = config.storefront_slug if config else ""
    store_type = config.store_type if config else "magalu"
    theme_color = config.theme_color if config else "#0088ff"
    tagline = config.tagline if config else "tem na minha loja"
    owner_avatar_b64 = config.owner_avatar_b64 if config else ""

    async def _send_approved_offer():
        try:
            copy = None
            if ai_service:
                try:
                    copy = await ai_service.generate_affiliate_copy(
                        title=log_title,
                        price=log_price,
                        old_price=log_old_price,
                        discount=log_discount,
                        link=log_short_url,
                        installment_text=log_installment,
                        pix_discount_text=log_pix_discount,
                    )
                except Exception:
                    pass

            if not copy:
                old_str = f"~~R$ {log_old_price:,.2f}~~ ".replace(",", "X").replace(".", ",").replace("X", ".") if log_old_price else ""
                copy = (
                    f"🔥 *{log_title}*\n\n"
                    f"{old_str}"
                    f"💰 *R$ {log_price:,.2f}*\n".replace(",", "X").replace(".", ",").replace("X", ".")
                    + (f"💳 {log_installment}\n" if log_installment else "")
                    + (f"💸 {log_pix_discount}\n\n" if log_pix_discount else "\n")
                    + f"👉 {log_short_url}"
                )

            card_bytes = await generate_promo_card(
                title=log_title,
                price=log_price,
                old_price=log_old_price,
                discount_percent=log_discount,
                image_url=log_image_url,
                storefront_name=storefront_slug,
                store_type=store_type,
                theme_color=theme_color,
                tagline=tagline,
                installment_text=log_installment,
                pix_discount_text=log_pix_discount,
                owner_avatar_b64=owner_avatar_b64,
            )
            
            if card_bytes:
                b64_img = base64.b64encode(card_bytes).decode("utf-8")
                await whatsapp.send_status(content=b64_img, type="image", caption=copy)
            else:
                await whatsapp.send_status(content=copy)
                
            with next(get_db()) as db_session:
                db_log = db_session.query(AffiliateLogModel).get(log_id_val)
                if db_log:
                    db_log.status = "sent"
                    db_session.commit()
                
        except Exception as e:
            logger.error(f"[affiliate] Failed to send approved offer: {e}")
            with next(get_db()) as db_session:
                db_log = db_session.query(AffiliateLogModel).get(log_id_val)
                if db_log:
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
