"""
Background scheduler and campaign execution tasks.
Runs in the FastAPI lifespan, managing scheduled and recurring campaigns.
"""

import asyncio
import json
import logging
import os
from datetime import timedelta
from core.infrastructure.utils.timezone import now_sp

from core.domain.entities import (
    Campaign,
    CampaignStatus as DomainCampaignStatus,
)
from core.infrastructure.database.models import (
    CampaignModel,
    StatusCampaignModel,
    InstanceModel,
    BroadcastCampaignModel,
    BirthdayTemplateModel,
    AffiliateConfigModel,
)
from core.infrastructure.database.repositories import (
    SQLCampaignRepository,
    SQLBroadcastCampaignRepository,
    SQLBroadcastListRepository,
    SQLTargetRepository,
)
from core.infrastructure.database.session import SessionLocal
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.application.use_cases.send_birthday_messages import SendBirthdayMessages
from core.application.use_cases.dispatch_status_offers import DispatchStatusOffers
from core.infrastructure.gateways.magalu_gateway import MagaluGateway
from core.infrastructure.gateways.mercadolivre_gateway import MercadoLivreGateway

logger = logging.getLogger(__name__)

# Global state to prevent duplicate scheduler runs for stateless tasks
_last_birthday_run = None
_affiliate_runs_by_user = {}


async def execute_campaign_task(campaign_id: int) -> None:
    """
    Runs a campaign in the background using its own database session.
    """
    db = SessionLocal()
    try:
        logger.info("executing background task for campaign id %s", campaign_id)
        campaign_repo = SQLCampaignRepository(db)

        model = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
        if not model:
            logger.error("campaign %s not found in background task", campaign_id)
            return

        domain_campaign = campaign_repo._to_entity(model)
        await send_campaign(domain_campaign, db)
    except Exception as e:
        logger.error(
            "error in background campaign task for %s: %s",
            campaign_id,
            e,
            exc_info=True,
        )
    finally:
        db.close()


async def send_campaign(campaign: Campaign, db) -> None:
    """
    Sends campaign messages via WhatsApp with humanized behavior.
    """
    from core.application.services.humanized_sender import HumanizedSender

    logger.info("sending campaign: %s", campaign.title)
    campaign_repo = SQLCampaignRepository(db)

    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == campaign.user_id)
        .first()
    )
    instance_name = instance_model.name if instance_model else None

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_model.apikey if instance_model else None,
    )
    humanized_sender = HumanizedSender(whatsapp_service)

    campaign.status = DomainCampaignStatus.SENDING
    campaign_repo.save(campaign)

    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    cloaked_link = f"{base_url}/l/{campaign.product.id}"

    message = campaign.custom_message
    if not message:
        message = f"Confira nosso produto: {campaign.product.name} - {cloaked_link}"
    else:
        message = message.replace("{{link}}", cloaked_link)
        message = message.replace(campaign.product.affiliate_link, cloaked_link)

    try:
        result = await humanized_sender.send_campaign_humanized(
            targets=campaign.target_groups,
            content=message,
            media_url=campaign.product.image_url,
            campaign_id=campaign.id,
            db=db,
        )
        # If it returns a dict, handle it. If it was paused/canceled mid-loop,
        # result['status'] will be 'paused' or 'canceled'.
        if isinstance(result, dict):
            status_map = {
                "completed": DomainCampaignStatus.SENT,
                "paused": DomainCampaignStatus.PAUSED,
                "canceled": DomainCampaignStatus.CANCELED,
            }
            campaign.status = status_map.get(result.get("status"), DomainCampaignStatus.FAILED)
        else:
            campaign.status = DomainCampaignStatus.SENT if result else DomainCampaignStatus.FAILED
    except Exception as e:
        logger.error("error during humanized campaign send: %s", e, exc_info=True)
        campaign.status = DomainCampaignStatus.FAILED

    campaign.sent_at = now_sp()
    campaign_repo.save(campaign)
    logger.info(
        "campaign '%s' finished with status: %s", campaign.title, campaign.status.name
    )


async def execute_status_campaign_task(campaign_id: int) -> None:
    try:
        logger.info("executing background task for status campaign id %s", campaign_id)
        await send_status_campaign(campaign_id)
    except Exception as e:
        logger.error(
            "error in background status task for %s: %s", campaign_id, e, exc_info=True
        )
        # use a fresh, independent session to recover
        recovery_db = SessionLocal()
        try:
            stuck = (
                recovery_db.query(StatusCampaignModel)
                .filter(StatusCampaignModel.id == campaign_id)
                .first()
            )
            if stuck:
                stuck.status = "failed"
                stuck.sent_at = now_sp()
                recovery_db.commit()
                logger.info(
                    "status campaign %s force-set to 'failed' via recovery session",
                    campaign_id,
                )
        except Exception as rec_err:
            logger.error(
                "recovery session also failed for campaign %s: %s", campaign_id, rec_err
            )
            recovery_db.rollback()
        finally:
            recovery_db.close()


async def send_status_campaign(campaign_id: int) -> None:
    """
    Sends a status campaign. Uses decoupled DB sessions to prevent IDLE
    transaction drops during the long Evolution API HTTP timeout.
    """
    db = SessionLocal()
    try:
        model = db.query(StatusCampaignModel).filter(StatusCampaignModel.id == campaign_id).first()
        if not model:
            logger.error("status campaign model %s not found inside send_status_campaign", campaign_id)
            return

        logger.info("sending status campaign: %s (id=%s)", model.title, campaign_id)

        instance_model = db.query(InstanceModel).filter(InstanceModel.id == model.instance_id).first()
        if not instance_model:
            logger.error("instance not found for status campaign %s", campaign_id)
            model.status = "failed"
            model.sent_at = now_sp()
            db.commit()
            return

        instance_name = instance_model.name
        instance_apikey = instance_model.apikey
        image_url = model.image_url
        caption = model.caption or ""
        bg_color = model.background_color or "#128C7E"
        target_contacts_raw = model.target_contacts
    finally:
        db.close()

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_apikey,
    )

    final_status = "failed"
    try:
        # resolve and optimize media
        from core.infrastructure.utils.image_utils import get_optimized_base64

        media_content = None
        if image_url:
            try:
                media_content = await get_optimized_base64(
                    image_url, max_size=(1080, 1920), quality=85
                )
                logger.info(
                    "status media successfully optimized for campaign %s", campaign_id
                )
            except Exception as e:
                logger.error("failed to optimize status media: %s", e)
                # fallback to raw url if optimization fails and it's an external url
                if image_url.startswith("http"):
                    media_content = image_url
                else:
                    logger.error("no fallback available for local image — marking as failed")
                    update_db = SessionLocal()
                    try:
                        update_model = update_db.query(StatusCampaignModel).get(campaign_id)
                        if update_model:
                            update_model.status = "failed"
                            update_model.sent_at = now_sp()
                            update_db.commit()
                    finally:
                        update_db.close()
                    return
        else:
            # for text-only statuses, the evolution api expects text in the 'content' field
            media_content = caption or " "

        # parse explicit target list (if any was set on the campaign)
        target_contacts = []
        if target_contacts_raw:
            try:
                target_contacts = json.loads(target_contacts_raw)
            except Exception:
                target_contacts = []

        # ── fix: when no explicit target list is set, use allContacts=True ──
        # this bypasses the broken get_contacts() sync issue in baileys.
        # the evolution api will broadcast to all contacts on the device.
        use_all_contacts = len(target_contacts) == 0
        if use_all_contacts:
            logger.info("status campaign %s: no explicit targets → using allContacts=True", campaign_id)

        if use_all_contacts:
            # single call with allContacts=True, no chunking needed
            success = await whatsapp_service.send_status(
                content=media_content,
                type="image" if image_url else "text",
                jid_list=[],  # empty list triggers allContacts=True in send_status
                backgroundColor=bg_color,
                caption=caption,
            )
        else:
            # explicit target list: send in chunks of 250
            # first send to owner jid separately for visual confirmation
            owner_jid = None
            try:
                status_info = await whatsapp_service.get_status()
                owner_jid = status_info.get("owner", "")
                if owner_jid and "@s.whatsapp.net" not in owner_jid:
                    owner_jid = f"{owner_jid}@s.whatsapp.net"
            except Exception as e:
                logger.warning("could not fetch owner jid for status: %s", e)

            if owner_jid:
                target_contacts = [jid for jid in target_contacts if jid != owner_jid]
                logger.info("sending isolated status to owner jid: %s", owner_jid)
                await whatsapp_service.send_status(
                    content=media_content,
                    type="image" if image_url else "text",
                    jid_list=[owner_jid],
                    backgroundColor=bg_color,
                    caption=caption,
                )
                await asyncio.sleep(5)

            chunk_size = 250
            success = True
            for i in range(0, len(target_contacts), chunk_size):
                chunk = target_contacts[i:i + chunk_size]
                logger.info("sending status chunk %s to %s targets...", (i // chunk_size) + 1, len(chunk))
                chunk_success = await whatsapp_service.send_status(
                    content=media_content,
                    type="image" if image_url else "text",
                    jid_list=chunk,
                    backgroundColor=bg_color,
                    caption=caption,
                )
                if not chunk_success:
                    success = False
                    logger.error("failed to send status chunk %s", (i // chunk_size) + 1)
                if i + chunk_size < len(target_contacts):
                    await asyncio.sleep(5)

        final_status = "sent" if success else "failed"
    except Exception as e:
        logger.error("error during status campaign send: %s", e, exc_info=True)
        final_status = "failed"

    # directly update the orm model row — avoids entity mapper + identity map cache
    update_db = SessionLocal()
    try:
        update_model = update_db.query(StatusCampaignModel).get(campaign_id)
        if update_model:
            update_model.status = final_status
            update_model.sent_at = now_sp()
            update_db.commit()
            logger.info(
                "status campaign '%s' (id=%s) finished with status: %s",
                update_model.title,
                campaign_id,
                final_status,
            )
    finally:
        update_db.close()


async def execute_broadcast_campaign_task(campaign_id: int) -> None:
    """
    Executes a broadcast campaign using ExecuteBroadcastCampaignUseCase.
    """
    from core.application.use_cases.execute_broadcast_campaign import (
        ExecuteBroadcastCampaignUseCase,
    )

    db = SessionLocal()
    try:
        logger.info("executing background broadcast campaign id %s", campaign_id)
        broadcast_repo = SQLBroadcastCampaignRepository(db)
        list_repo = SQLBroadcastListRepository(db)
        target_repo = SQLTargetRepository(db)

        use_case = ExecuteBroadcastCampaignUseCase(
            db_session=db,
            broadcast_repo=broadcast_repo,
            list_repo=list_repo,
            target_repo=target_repo,
        )
        await use_case.execute(campaign_id)
    except Exception as e:
        logger.error(
            "error in background broadcast task for %s: %s",
            campaign_id,
            e,
            exc_info=True,
        )
    finally:
        db.close()


async def execute_birthday_task(user_id: int) -> None:
    """Executes the daily birthday message dispatch for a specific user."""
    db = SessionLocal()
    try:
        use_case = SendBirthdayMessages(db=db, user_id=user_id)
        await use_case.execute()
    except Exception as e:
        logger.error("error in background birthday task for user %s: %s", user_id, e, exc_info=True)
    finally:
        db.close()


async def execute_affiliate_task(
    user_id: int, instance_name: str, instance_apikey: str,
    storefront_slug: str, categories: list[str],
    min_discount: float, max_offers: int,
    store_type: str = "magalu",
    theme_color: str = "#0088ff",
    tagline: str = "tem na minha loja",
    owner_avatar_b64: str = "",
    # ml affiliate params
    ml_profile_slug: str = "",
    ml_enabled: bool = False,
    ml_categories: list[str] | None = None,
) -> None:
    """Executes the affiliate offer dispatch for a specific user (status)."""
    whatsapp = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_apikey,
    )

    ai_service = None
    try:
        from core.infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
    except Exception:
        pass

    # ── collect offers from magalu ────────────────────────────────────
    all_offers = []

    if storefront_slug:
        try:
            magalu_gw = MagaluGateway(storefront_slug=storefront_slug)
            magalu_offers = await magalu_gw.get_offers(
                categories=categories,
                min_discount_percent=min_discount,
                max_offers=max_offers,
            )
            # wrap MagaluOffer as a generic dict for unified processing
            for o in magalu_offers:
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
            logger.error("[affiliate-scheduler] magalu fetch error: %s", e)

    # ── collect offers from mercado livre ─────────────────────────────
    if ml_enabled and ml_profile_slug:
        try:
            ml_gw = MercadoLivreGateway(profile_slug=ml_profile_slug)
            ml_offers = await ml_gw.get_offers(
                categories=ml_categories or categories,
                min_discount_percent=min_discount,
                max_offers=max_offers,
            )
            for o in ml_offers:
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
            logger.error("[affiliate-scheduler] ml fetch error: %s", e)

    try:
        offers = all_offers

        if not offers:
            logger.info("[affiliate-scheduler] no qualifying offers for user %s", user_id)
            return

        from core.infrastructure.utils.shortener import get_or_create_shortlink
        from core.infrastructure.database.session import SessionLocal as _SessionLocal

        for offer in offers:
            # build status message
            db = _SessionLocal()
            try:
                short_link_url = get_or_create_shortlink(
                    db,
                    offer["affiliate_link"],
                    offer.get("source", storefront_slug or "affiliate"),
                )
            finally:
                db.close()
            
            copy = None
            if ai_service:
                try:
                    copy = await ai_service.generate_affiliate_copy(
                        title=offer["title"],
                        price=offer["price"],
                        old_price=offer["old_price"],
                        discount=offer["discount_percent"],
                        link=short_link_url,
                    )
                except Exception:
                    pass

            if not copy:
                old_fmt = ""
                if offer.get("old_price"):
                    old_fmt = f"~~R$ {offer['old_price']:,.2f}~~  ".replace(",", "X").replace(".", ",").replace("X", ".")
                price_fmt = f"R$ {offer['price']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                copy = (
                    f"🔥 *{offer['title']}*\n\n"
                    f"{old_fmt}💰 *{price_fmt}*\n"
                    f"📉 *{offer['discount_percent']:.0f}% OFF*\n\n"
                    f"👉 {short_link_url}"
                )

            try:
                import base64
                from core.infrastructure.image.promo_card_generator import generate_promo_card
                card_bytes = await generate_promo_card(
                    title=offer["title"],
                    price=offer["price"],
                    old_price=offer["old_price"],
                    discount_percent=offer["discount_percent"],
                    image_url=offer["image_url"],
                    storefront_name=storefront_slug or offer.get("source", "loja"),
                    store_type=store_type,
                    theme_color=theme_color,
                    tagline=tagline,
                    installment_text=offer.get("installment_text", ""),
                    pix_discount_text=offer.get("pix_discount_text", ""),
                    owner_avatar_b64=owner_avatar_b64,
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
                logger.error("[affiliate-scheduler] error generating card: %s", e)
                # fallback to text only
                await whatsapp.send_status(content=copy)

            logger.info(
                "[affiliate-scheduler] posted [%s]: %s (%.0f%% off)",
                offer.get("source", "?"),
                offer["title"][:40],
                offer["discount_percent"],
            )
            await asyncio.sleep(5)

        logger.info("[affiliate-scheduler] dispatch complete for user %s: %d offers", user_id, len(offers))
    except Exception as e:
        logger.error("error in background affiliate task for user %s: %s", user_id, e, exc_info=True)


async def execute_affiliate_group_task(
    user_id: int, instance_name: str, instance_apikey: str,
    storefront_slug: str, categories: list[str],
    min_discount: float, max_offers: int,
    group_jids: list[str],
    theme_color: str = "#0088ff",
    tagline: str = "tem na minha loja",
    store_type: str = "magalu",
    owner_avatar_b64: str = "",
    ml_profile_slug: str = "",
    ml_enabled: bool = False,
) -> None:
    """Sends affiliate electronics offers directly to WhatsApp groups."""
    if not group_jids:
        logger.info("[group-scheduler] no groups configured for user %s — skipping", user_id)
        return

    whatsapp = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_apikey,
    )

    ai_service = None
    try:
        from core.infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
    except Exception:
        pass

    # ── collect offers from magalu + ml ──────────────────────────────
    all_offers: list[dict] = []

    if storefront_slug:
        try:
            magalu_gw = MagaluGateway(storefront_slug=storefront_slug)
            magalu_offers = await magalu_gw.get_offers(
                categories=categories,
                min_discount_percent=min_discount,
                max_offers=max_offers,
            )
            for o in magalu_offers:
                all_offers.append({
                    "title": o.title, "price": o.price, "old_price": o.old_price,
                    "discount_percent": o.discount_percent, "image_url": o.image_url,
                    "affiliate_link": o.affiliate_link, "installment_text": o.installment_text,
                    "pix_discount_text": o.pix_discount_text, "source": "magalu",
                })
        except Exception as e:
            logger.error("[group-scheduler] magalu fetch error: %s", e)

    if ml_enabled and ml_profile_slug:
        try:
            ml_gw = MercadoLivreGateway(profile_slug=ml_profile_slug)
            ml_offers = await ml_gw.get_offers(
                min_discount_percent=min_discount,
                max_offers=max_offers,
            )
            for o in ml_offers:
                all_offers.append({
                    "title": o.title, "price": o.price, "old_price": o.old_price,
                    "discount_percent": o.discount_percent, "image_url": o.image_url,
                    "affiliate_link": o.affiliate_link, "installment_text": o.installment_text,
                    "pix_discount_text": "", "source": "mercadolivre",
                })
        except Exception as e:
            logger.error("[group-scheduler] ml fetch error: %s", e)

    if not all_offers:
        logger.info("[group-scheduler] no offers found for user %s — skipping", user_id)
        return

    from core.infrastructure.utils.shortener import get_or_create_shortlink
    from core.infrastructure.database.session import SessionLocal as _SessionLocal
    import base64
    from core.infrastructure.image.promo_card_generator import generate_promo_card

    for offer in all_offers[:max_offers]:
        db = _SessionLocal()
        try:
            short_link_url = get_or_create_shortlink(
                db,
                offer["affiliate_link"],
                offer.get("source", "affiliate"),
            )
        finally:
            db.close()

        copy = None
        if ai_service:
            try:
                copy = await ai_service.generate_affiliate_copy(
                    title=offer["title"],
                    price=offer["price"],
                    old_price=offer["old_price"],
                    discount=offer["discount_percent"],
                    link=short_link_url,
                )
            except Exception:
                pass

        if not copy:
            old_fmt = ""
            if offer.get("old_price"):
                old_fmt = (
                    f"~~R$ {offer['old_price']:,.2f}~~  "
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
            price_fmt = f"R$ {offer['price']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            source_label = "🏪 Magalu" if offer.get("source") == "magalu" else "🛒 Mercado Livre"
            copy = (
                f"🔥 *OFERTA {source_label}*\n\n"
                f"*{offer['title']}*\n\n"
                f"{old_fmt}💰 *{price_fmt}*\n"
                f"📉 *{offer['discount_percent']:.0f}% OFF*\n"
                + (f"💳 {offer['installment_text']}\n" if offer.get("installment_text") else "")
                + f"\n👉 {short_link_url}"
            )

        # try to generate promo card image; fall back to text if it fails
        try:
            card_bytes = await generate_promo_card(
                title=offer["title"],
                price=offer["price"],
                old_price=offer["old_price"],
                discount_percent=offer["discount_percent"],
                image_url=offer["image_url"],
                storefront_name=storefront_slug or offer.get("source", "loja"),
                store_type=store_type,
                theme_color=theme_color,
                tagline=tagline,
                installment_text=offer.get("installment_text", ""),
                pix_discount_text=offer.get("pix_discount_text", ""),
                owner_avatar_b64=owner_avatar_b64,
            )
            if not card_bytes:
                raise ValueError("card_bytes is empty")
        except Exception as e:
            logger.warning("[group-scheduler] card generation failed: %s — using image url directly", e)
            card_bytes = None

        for group_jid in group_jids:
            try:
                if card_bytes:
                    b64_img = base64.b64encode(card_bytes).decode("utf-8")
                    await whatsapp.send_image(group_jid, f"data:image/jpeg;base64,{b64_img}", caption=copy)
                elif offer.get("image_url"):
                    await whatsapp.send_image(group_jid, offer["image_url"], caption=copy)
                else:
                    await whatsapp.send_text(group_jid, copy)
                logger.info("[group-scheduler] sent to group %s: %s", group_jid[:20], offer["title"][:40])
            except Exception as e:
                logger.error("[group-scheduler] error sending to group %s: %s", group_jid[:20], e)

            await asyncio.sleep(3)  # small delay between groups

        await asyncio.sleep(8)  # delay between offers

    logger.info("[group-scheduler] group dispatch complete for user %s", user_id)


async def execute_manual_selected_dispatch(
    user_id: int,
    instance_name: str,
    instance_apikey: str,
    offers_data: list[dict],
    targets: list[str],
    config_snapshot: dict,
) -> None:
    """
    dispatches a manually-selected list of offers to the chosen targets.

    offers_data: list of offer dicts (title, price, old_price, discount_percent,
                 image_url, affiliate_link, installment_text, pix_discount_text, source).
    targets: list of destination strings — 'status' and/or 'groups'.
    config_snapshot: dict with store config fields needed for card generation:
                     store_type, theme_color, tagline, owner_avatar_b64,
                     storefront_slug, group_jids (list[str]).
    """
    if not offers_data:
        logger.info("[manual-dispatch] no offers provided for user %s", user_id)
        return
    if not targets:
        logger.info("[manual-dispatch] no targets provided for user %s", user_id)
        return

    whatsapp = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_apikey,
    )

    ai_service = None
    try:
        from core.infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
    except Exception:
        pass

    from core.infrastructure.utils.shortener import get_or_create_shortlink
    from core.infrastructure.database.session import SessionLocal as _SessionLocal
    from core.infrastructure.database.models import AffiliateLogModel as _Log
    import base64
    from core.infrastructure.image.promo_card_generator import generate_promo_card

    send_to_status = "status" in targets
    send_to_groups = "groups" in targets
    group_jids: list[str] = config_snapshot.get("group_jids") or []

    store_type = config_snapshot.get("store_type", "magalu")
    theme_color = config_snapshot.get("theme_color", "#0088ff")
    tagline = config_snapshot.get("tagline", "tem na minha loja")
    owner_avatar_b64 = config_snapshot.get("owner_avatar_b64", "")
    storefront_slug = config_snapshot.get("storefront_slug", "")

    for offer in offers_data:
        # ── build short link ──────────────────────────────────────────
        db = _SessionLocal()
        try:
            short_link_url = get_or_create_shortlink(
                db,
                offer["affiliate_link"],
                offer.get("source", storefront_slug or "affiliate"),
            )
        finally:
            db.close()

        # ── build copy text ───────────────────────────────────────────
        copy = None
        if ai_service:
            try:
                copy = await ai_service.generate_affiliate_copy(
                    title=offer["title"],
                    price=offer["price"],
                    old_price=offer.get("old_price"),
                    discount=offer["discount_percent"],
                    link=short_link_url,
                )
            except Exception:
                pass

        if not copy:
            old_fmt = ""
            if offer.get("old_price"):
                old_fmt = (
                    f"~~R$ {offer['old_price']:,.2f}~~  "
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
            price_fmt = f"R$ {offer['price']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            source_label = "🏪 Magalu" if offer.get("source") == "magalu" else "🛒 Mercado Livre"
            copy = (
                f"🔥 *OFERTA {source_label}*\n\n"
                f"*{offer['title']}*\n\n"
                f"{old_fmt}💰 *{price_fmt}*\n"
                f"📉 *{offer['discount_percent']:.0f}% OFF*\n"
                + (f"💳 {offer['installment_text']}\n" if offer.get("installment_text") else "")
                + f"\n👉 {short_link_url}"
            )

        # ── generate promo card ───────────────────────────────────────
        card_bytes = None
        try:
            card_bytes = await generate_promo_card(
                title=offer["title"],
                price=offer["price"],
                old_price=offer.get("old_price"),
                discount_percent=offer["discount_percent"],
                image_url=offer.get("image_url", ""),
                storefront_name=storefront_slug or offer.get("source", "loja"),
                store_type=store_type,
                theme_color=theme_color,
                tagline=tagline,
                installment_text=offer.get("installment_text", ""),
                pix_discount_text=offer.get("pix_discount_text", ""),
                owner_avatar_b64=owner_avatar_b64,
            )
        except Exception as e:
            logger.warning("[manual-dispatch] card generation failed: %s", e)

        b64_img = base64.b64encode(card_bytes).decode("utf-8") if card_bytes else None

        # ── send to status ────────────────────────────────────────────
        if send_to_status:
            try:
                if b64_img:
                    await whatsapp.send_status(
                        content=b64_img,
                        type="image",
                        caption=copy,
                    )
                else:
                    await whatsapp.send_status(content=copy)
                logger.info("[manual-dispatch] sent to status: %s", offer["title"][:40])
            except Exception as e:
                logger.error("[manual-dispatch] error sending to status: %s", e)

        # ── send to groups ────────────────────────────────────────────
        if send_to_groups and group_jids:
            for jid in group_jids:
                try:
                    if b64_img:
                        await whatsapp.send_image(jid, f"data:image/jpeg;base64,{b64_img}", caption=copy)
                    elif offer.get("image_url"):
                        await whatsapp.send_image(jid, offer["image_url"], caption=copy)
                    else:
                        await whatsapp.send_text(jid, copy)
                    logger.info("[manual-dispatch] sent to group %s: %s", jid[:20], offer["title"][:40])
                except Exception as e:
                    logger.error("[manual-dispatch] error sending to group %s: %s", jid[:20], e)
                await asyncio.sleep(2)

        # ── log to db ─────────────────────────────────────────────────
        db = _SessionLocal()
        try:
            db.add(_Log(
                user_id=user_id,
                product_title=offer["title"],
                image_url=offer.get("image_url", ""),
                original_url=offer["affiliate_link"],
                short_url=short_link_url,
                price=offer["price"],
                old_price=offer.get("old_price"),
                discount_percent=offer["discount_percent"],
                installment_text=offer.get("installment_text", ""),
                source=offer.get("source", "magalu"),
                status="sent",
            ))
            db.commit()
        finally:
            db.close()

        await asyncio.sleep(5)  # delay between offers

    logger.info(
        "[manual-dispatch] complete for user %s: %d offers → targets: %s",
        user_id, len(offers_data), targets,
    )


async def campaign_scheduler_loop() -> None:
    """
    Background task that checks and dispatches scheduled/recurring campaigns every minute.
    """
    logger.info("starting campaign scheduler loop")
    while True:
        # Give some time for migrations/startup to complete if needed
        db = SessionLocal()
        
        # Keep-alive ping for Evolution API on Render (prevents sleep)
        try:
            import httpx
            import os
            base_url = os.environ.get("EVOLUTION_API_URL", "http://evolution-api:8080").rstrip("/")
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.get(base_url)
        except Exception as ping_err:
            logger.debug(f"Evolution API ping failed: {ping_err}")
            
        try:
            # Check if tables exist before querying (basic resilience)
            # This prevents sqlite3.OperationalError: no such table: campaigns
            from sqlalchemy import inspect

            inspector = inspect(db.bind)
            if not inspector.has_table("campaigns"):
                logger.warning(
                    "scheduler: 'campaigns' table not found yet. skipping this tick."
                )
                db.close()
                await asyncio.sleep(10)
                continue

            now = now_sp()
            current_time_str = now.strftime("%H:%M")
            current_day_str = now.strftime("%a").lower()

            # birthday check (runs once per day at 09:00)
            global _last_birthday_run
            if current_time_str == "09:00" and _last_birthday_run != now.strftime("%Y-%m-%d"):
                _last_birthday_run = now.strftime("%Y-%m-%d")
                logger.info("scheduler: running daily birthday check")
                active_templates = db.query(BirthdayTemplateModel).filter(BirthdayTemplateModel.is_enabled == True).all()
                for tpl in active_templates:
                    asyncio.create_task(execute_birthday_task(tpl.user_id))

            # affiliate check (runs at configured hours)
            global _affiliate_runs_by_user
            active_affiliate_configs = db.query(AffiliateConfigModel).all()
            for config in active_affiliate_configs:
                has_magalu = bool(config.storefront_slug)
                has_ml = bool(config.ml_enabled and config.ml_profile_slug)

                if not has_magalu and not has_ml:
                    continue

                categories = [c.strip() for c in (config.categories or "notebook,celular").split(",") if c.strip()]
                ml_categories = [c.strip() for c in (config.ml_categories or "notebook,celular").split(",") if c.strip()]
                current_run_signature = f"{now.strftime('%Y-%m-%d')} {current_time_str}"

                # ── status dispatch (magalu + ml → whatsapp status) ─────
                dispatch_hours_str = config.dispatch_hours or "9,12,18"
                dispatch_hours = [f"{h.strip().zfill(2)}:00" for h in dispatch_hours_str.split(",")]
                user_last_run = _affiliate_runs_by_user.get(config.user_id)

                if current_time_str in dispatch_hours and user_last_run != current_run_signature:
                    _affiliate_runs_by_user[config.user_id] = current_run_signature
                    logger.info("scheduler: running affiliate status dispatch for user %s at %s", config.user_id, current_time_str)

                    instance = db.query(InstanceModel).filter(
                        InstanceModel.user_id == config.user_id,
                        InstanceModel.status == "connected",
                    ).first()
                    if instance:
                        asyncio.create_task(execute_affiliate_task(
                            user_id=config.user_id,
                            instance_name=instance.name,
                            instance_apikey=instance.apikey,
                            storefront_slug=config.storefront_slug or "",
                            categories=categories,
                            min_discount=config.min_discount_percent,
                            max_offers=config.max_offers_per_run,
                            store_type=config.store_type or "magalu",
                            theme_color=config.theme_color or "#0088ff",
                            tagline=config.tagline or "tem na minha loja",
                            owner_avatar_b64=config.owner_avatar_b64 or "",
                            ml_profile_slug=config.ml_profile_slug or "",
                            ml_enabled=config.ml_enabled or False,
                            ml_categories=ml_categories,
                        ))

                # ── group dispatch (magalu + ml → grupos) ───────────────
                if config.group_enabled and config.group_jids:
                    import json as _json
                    try:
                        group_jids = _json.loads(config.group_jids)
                    except Exception:
                        group_jids = []

                    group_hours_str = config.group_dispatch_hours or "9,12,15,18,21"
                    group_hours = [f"{h.strip().zfill(2)}:00" for h in group_hours_str.split(",")]
                    group_run_key = f"group_{config.user_id}"
                    group_last_run = _affiliate_runs_by_user.get(group_run_key)
                    group_run_signature = f"{now.strftime('%Y-%m-%d')} {current_time_str}"

                    if current_time_str in group_hours and group_last_run != group_run_signature and group_jids:
                        _affiliate_runs_by_user[group_run_key] = group_run_signature
                        logger.info("scheduler: running affiliate group dispatch for user %s at %s", config.user_id, current_time_str)

                        instance = instance or db.query(InstanceModel).filter(
                            InstanceModel.user_id == config.user_id,
                            InstanceModel.status == "connected",
                        ).first()
                        if instance:
                            asyncio.create_task(execute_affiliate_group_task(
                                user_id=config.user_id,
                                instance_name=instance.name,
                                instance_apikey=instance.apikey,
                                storefront_slug=config.storefront_slug or "",
                                categories=categories,
                                min_discount=config.min_discount_percent,
                                max_offers=config.max_offers_per_run,
                                group_jids=group_jids,
                                theme_color=config.theme_color or "#0088ff",
                                tagline=config.tagline or "tem na minha loja",
                                store_type=config.store_type or "magalu",
                                owner_avatar_b64=config.owner_avatar_b64 or "",
                                ml_profile_slug=config.ml_profile_slug or "",
                                ml_enabled=config.ml_enabled or False,
                            ))

            # one-off campaigns
            one_off_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.status == "scheduled",
                    ~CampaignModel.is_recurring,
                    CampaignModel.scheduled_at <= now,
                )
                .all()
            )

            for campaign_model in one_off_campaigns:
                logger.info(
                    "scheduling one-off campaign task: %s", campaign_model.title
                )
                campaign_model.status = "sending"
                campaign_model.last_run_at = now
                db.add(campaign_model)
                db.commit()
                asyncio.create_task(execute_campaign_task(campaign_model.id))

            # one-off STATUS campaigns
            one_off_statuses = (
                db.query(StatusCampaignModel)
                .filter(
                    StatusCampaignModel.status == "scheduled",
                    ~StatusCampaignModel.is_recurring,
                    StatusCampaignModel.scheduled_at <= now,
                )
                .all()
            )
            for status_model in one_off_statuses:
                logger.info(
                    "scheduling one-off status campaign task: %s", status_model.title
                )
                status_model.status = "sending"
                status_model.last_run_at = now
                db.add(status_model)
                db.commit()
                asyncio.create_task(execute_status_campaign_task(status_model.id))

            # one-off BROADCAST campaigns
            one_off_broadcasts = (
                db.query(BroadcastCampaignModel)
                .filter(
                    BroadcastCampaignModel.status == "scheduled",
                    ~BroadcastCampaignModel.is_recurring,
                    BroadcastCampaignModel.scheduled_at <= now,
                )
                .all()
            )
            for bc_model in one_off_broadcasts:
                logger.info("scheduling one-off broadcast task: %s", bc_model.title)
                bc_model.status = "sending"
                bc_model.last_run_at = now
                db.add(bc_model)
                db.commit()
                asyncio.create_task(execute_broadcast_campaign_task(bc_model.id))

            # recurring campaigns
            recurring_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.is_recurring,
                    CampaignModel.status.notin_(["failed", "paused", "canceled"]),
                )
                .all()
            )

            for campaign_model in recurring_campaigns:
                if not campaign_model.recurrence_days:
                    continue
                if current_day_str not in campaign_model.recurrence_days.lower():
                    continue

                target_config = {}
                if campaign_model.target_config:
                    try:
                        target_config = json.loads(campaign_model.target_config)
                    except Exception as exc:
                        logger.warning(
                            "failed to parse target_config for campaign %s: %s",
                            campaign_model.id,
                            exc,
                        )

                send_times = [
                    t.strip()
                    for t in (campaign_model.send_time or "").split(",")
                    if t.strip()
                ]

                if current_time_str in send_times:
                    if (
                        not campaign_model.last_run_at
                        or campaign_model.last_run_at.strftime("%Y-%m-%d %H:%M")
                        != now.strftime("%Y-%m-%d %H:%M")
                    ):
                        logger.info(
                            "executing recurring campaign: %s at %s",
                            campaign_model.title,
                            current_time_str,
                        )
                        campaign_model.status = "sending"
                        campaign_model.last_run_at = now
                        db.add(campaign_model)
                        db.commit()
                        asyncio.create_task(execute_campaign_task(campaign_model.id))

                for target_type, t_schedule in target_config.items():
                    scheduled_times = (
                        [t_schedule] if isinstance(t_schedule, str) else t_schedule
                    )
                    if current_time_str in scheduled_times:
                        if (
                            not campaign_model.last_run_at
                            or campaign_model.last_run_at.strftime("%Y-%m-%d %H:%M")
                            != now.strftime("%Y-%m-%d %H:%M")
                        ):
                            logger.info(
                                "executing granular campaign (%s): %s at %s",
                                target_type,
                                campaign_model.title,
                                current_time_str,
                            )
                            campaign_model.status = "sending"
                            campaign_model.last_run_at = now
                            db.add(campaign_model)
                            db.commit()
                            asyncio.create_task(
                                execute_campaign_task(campaign_model.id)
                            )

            # recurring STATUS campaigns
            # exclude 'sending' to avoid re-dispatching campaigns already in-flight
            recurring_statuses = (
                db.query(StatusCampaignModel)
                .filter(
                    StatusCampaignModel.is_recurring,
                    StatusCampaignModel.status.notin_(["failed", "sending", "paused", "canceled"]),
                )
                .all()
            )
            for status_model in recurring_statuses:
                if not status_model.recurrence_days:
                    continue
                if current_day_str not in status_model.recurrence_days.lower():
                    continue

                send_times = [
                    t.strip()
                    for t in (status_model.send_time or "").split(",")
                    if t.strip()
                ]
                if current_time_str in send_times:
                    if (
                        not status_model.last_run_at
                        or status_model.last_run_at.strftime("%Y-%m-%d %H:%M")
                        != now.strftime("%Y-%m-%d %H:%M")
                    ):
                        logger.info(
                            "executing recurring status: %s at %s",
                            status_model.title,
                            current_time_str,
                        )
                        status_model.status = "sending"
                        status_model.last_run_at = now
                        db.add(status_model)
                        db.commit()
                        asyncio.create_task(
                            execute_status_campaign_task(status_model.id)
                        )

            # safety net: auto-recover any status campaign stuck in 'sending' for over 10 minutes
            ten_minutes_ago = now - timedelta(minutes=10)
            stuck_statuses = (
                db.query(StatusCampaignModel)
                .filter(
                    StatusCampaignModel.status == "sending",
                    StatusCampaignModel.last_run_at <= ten_minutes_ago,
                )
                .all()
            )
            for stuck in stuck_statuses:
                logger.warning(
                    "status campaign %s stuck in 'sending' for >10min — auto-recovering to 'failed'",
                    stuck.id,
                )
                stuck.status = "failed"
                stuck.sent_at = stuck.sent_at or now
                db.add(stuck)
            if stuck_statuses:
                db.commit()

            # recurring BROADCAST campaigns
            recurring_broadcasts = (
                db.query(BroadcastCampaignModel)
                .filter(
                    BroadcastCampaignModel.is_recurring,
                    BroadcastCampaignModel.status.notin_(["failed", "paused", "canceled"]),
                )
                .all()
            )
            for bc_model in recurring_broadcasts:
                if not bc_model.recurrence_days:
                    continue
                if current_day_str not in bc_model.recurrence_days.lower():
                    continue

                send_times = [
                    t.strip()
                    for t in (bc_model.send_time or "").split(",")
                    if t.strip()
                ]
                if current_time_str in send_times:
                    if not bc_model.last_run_at or bc_model.last_run_at.strftime(
                        "%Y-%m-%d %H:%M"
                    ) != now.strftime("%Y-%m-%d %H:%M"):
                        logger.info(
                            "executing recurring broadcast: %s at %s",
                            bc_model.title,
                            current_time_str,
                        )
                        bc_model.status = "sending"
                        bc_model.last_run_at = now
                        db.add(bc_model)
                        db.commit()
                        asyncio.create_task(
                            execute_broadcast_campaign_task(bc_model.id)
                        )

        except Exception as e:
            logger.error("error in scheduler loop: %s", e, exc_info=True)
        finally:
            db.expire_all()
            db.close()

        await asyncio.sleep(30)
