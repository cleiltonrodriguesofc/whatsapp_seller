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
)
from core.infrastructure.database.repositories import (
    SQLCampaignRepository,
    SQLBroadcastCampaignRepository,
    SQLBroadcastListRepository,
    SQLTargetRepository,
)
from core.infrastructure.database.session import SessionLocal
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService

logger = logging.getLogger(__name__)


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
        logger.error("error in background campaign task for %s: %s", campaign_id, e, exc_info=True)
    finally:
        db.close()


async def send_campaign(campaign: Campaign, db) -> None:
    """
    Sends campaign messages via WhatsApp with humanized behavior.
    """
    from core.application.services.humanized_sender import HumanizedSender

    logger.info("sending campaign: %s", campaign.title)
    campaign_repo = SQLCampaignRepository(db)

    instance_model = db.query(InstanceModel).filter(InstanceModel.user_id == campaign.user_id).first()
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
        success = await humanized_sender.send_campaign_humanized(
            targets=campaign.target_groups,
            content=message,
            media_url=campaign.product.image_url,
        )
        campaign.status = DomainCampaignStatus.SENT if success else DomainCampaignStatus.FAILED
    except Exception as e:
        logger.error("error during humanized campaign send: %s", e, exc_info=True)
        campaign.status = DomainCampaignStatus.FAILED

    campaign.sent_at = now_sp()
    campaign_repo.save(campaign)
    logger.info("campaign '%s' finished with status: %s", campaign.title, campaign.status.name)


async def execute_status_campaign_task(campaign_id: int) -> None:
    db = SessionLocal()
    try:
        logger.info("executing background task for status campaign id %s", campaign_id)
        model = db.query(StatusCampaignModel).filter(StatusCampaignModel.id == campaign_id).first()
        if not model:
            logger.error("status campaign %s not found", campaign_id)
            return

        # expire the model so the identity map cache is cleared before send
        db.expire(model)
        await send_status_campaign(campaign_id, db)
    except Exception as e:
        logger.error("error in background status task for %s: %s", campaign_id, e, exc_info=True)
        # use a fresh, independent session so a corrupted/rolled-back session
        # never leaves the record permanently stuck in 'sending'
        recovery_db = SessionLocal()
        try:
            stuck = recovery_db.query(StatusCampaignModel).filter(
                StatusCampaignModel.id == campaign_id
            ).first()
            if stuck:
                stuck.status = "failed"
                stuck.sent_at = now_sp()
                recovery_db.commit()
                logger.info("status campaign %s force-set to 'failed' via recovery session", campaign_id)
        except Exception as rec_err:
            logger.error("recovery session also failed for campaign %s: %s", campaign_id, rec_err)
            recovery_db.rollback()
        finally:
            recovery_db.close()
    finally:
        db.close()


async def send_status_campaign(campaign_id: int, db) -> None:
    """
    Sends a status campaign. Accepts campaign_id instead of entity to avoid
    SQLAlchemy identity-map cache staleness that left records stuck in 'sending'.
    """
    # always reload the model from db to avoid stale identity-map cache
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

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )

    final_status = "failed"
    try:
        # resolve and optimize media
        from core.infrastructure.utils.image_utils import get_optimized_base64

        media_content = None
        if model.image_url:
            try:
                media_content = await get_optimized_base64(model.image_url, max_size=(1080, 1920), quality=85)
                logger.info("status media successfully optimized for campaign %s", campaign_id)
            except Exception as e:
                logger.error("failed to optimize status media: %s", e)
                # fallback to raw url if optimization fails and it's an external url
                if model.image_url.startswith("http"):
                    media_content = model.image_url
                else:
                    logger.error("no fallback available for local image — marking as failed")
                    model.status = "failed"
                    model.sent_at = now_sp()
                    db.commit()
                    return
        else:
            # for text-only statuses, the evolution api expects text in the 'content' field
            media_content = model.caption or " "

        target_contacts = []
        if model.target_contacts:
            try:
                target_contacts = json.loads(model.target_contacts)
            except Exception:
                target_contacts = []

        success = await whatsapp_service.send_status(
            content=media_content,
            type="image" if model.image_url else "text",
            jid_list=target_contacts if target_contacts else None,
            backgroundColor=model.background_color or "#128C7E",
            caption=model.caption or "",
        )
        final_status = "sent" if success else "failed"
    except Exception as e:
        logger.error("error during status campaign send: %s", e, exc_info=True)
        final_status = "failed"

    # directly update the orm model row — avoids entity mapper + identity map cache
    model.status = final_status
    model.sent_at = now_sp()
    db.commit()
    logger.info("status campaign '%s' (id=%s) finished with status: %s", model.title, campaign_id, final_status)


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
        logger.error("error in background broadcast task for %s: %s", campaign_id, e, exc_info=True)
    finally:
        db.close()


async def campaign_scheduler_loop() -> None:
    """
    Background task that checks and dispatches scheduled/recurring campaigns every minute.
    """
    while True:
        db = SessionLocal()
        try:
            now = now_sp()
            current_time_str = now.strftime("%H:%M")
            current_day_str = now.strftime("%a").lower()

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
                logger.info("scheduling one-off campaign task: %s", campaign_model.title)
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
                logger.info("scheduling one-off status campaign task: %s", status_model.title)
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
                    CampaignModel.status != "failed",
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

                send_times = [t.strip() for t in (campaign_model.send_time or "").split(",") if t.strip()]

                if current_time_str in send_times:
                    if not campaign_model.last_run_at or campaign_model.last_run_at.strftime(
                        "%Y-%m-%d %H:%M"
                    ) != now.strftime("%Y-%m-%d %H:%M"):
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
                    scheduled_times = [t_schedule] if isinstance(t_schedule, str) else t_schedule
                    if current_time_str in scheduled_times:
                        if not campaign_model.last_run_at or campaign_model.last_run_at.strftime(
                            "%Y-%m-%d %H:%M"
                        ) != now.strftime("%Y-%m-%d %H:%M"):
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
                            asyncio.create_task(execute_campaign_task(campaign_model.id))

            # recurring STATUS campaigns
            # exclude 'sending' to avoid re-dispatching campaigns already in-flight
            recurring_statuses = (
                db.query(StatusCampaignModel)
                .filter(
                    StatusCampaignModel.is_recurring,
                    StatusCampaignModel.status.notin_(["failed", "sending"]),
                )
                .all()
            )
            for status_model in recurring_statuses:
                if not status_model.recurrence_days:
                    continue
                if current_day_str not in status_model.recurrence_days.lower():
                    continue

                send_times = [t.strip() for t in (status_model.send_time or "").split(",") if t.strip()]
                if current_time_str in send_times:
                    if not status_model.last_run_at or status_model.last_run_at.strftime(
                        "%Y-%m-%d %H:%M"
                    ) != now.strftime("%Y-%m-%d %H:%M"):
                        logger.info("executing recurring status: %s at %s", status_model.title, current_time_str)
                        status_model.status = "sending"
                        status_model.last_run_at = now
                        db.add(status_model)
                        db.commit()
                        asyncio.create_task(execute_status_campaign_task(status_model.id))

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
                    BroadcastCampaignModel.status != "failed",
                )
                .all()
            )
            for bc_model in recurring_broadcasts:
                if not bc_model.recurrence_days:
                    continue
                if current_day_str not in bc_model.recurrence_days.lower():
                    continue

                send_times = [t.strip() for t in (bc_model.send_time or "").split(",") if t.strip()]
                if current_time_str in send_times:
                    if not bc_model.last_run_at or bc_model.last_run_at.strftime(
                        "%Y-%m-%d %H:%M"
                    ) != now.strftime("%Y-%m-%d %H:%M"):
                        logger.info("executing recurring broadcast: %s at %s", bc_model.title, current_time_str)
                        bc_model.status = "sending"
                        bc_model.last_run_at = now
                        db.add(bc_model)
                        db.commit()
                        asyncio.create_task(execute_broadcast_campaign_task(bc_model.id))

        except Exception as e:
            logger.error("error in scheduler loop: %s", e, exc_info=True)
        finally:
            db.close()

        await asyncio.sleep(15)
