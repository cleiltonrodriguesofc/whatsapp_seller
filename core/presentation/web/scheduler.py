"""
Background scheduler and campaign execution tasks.
Runs in the FastAPI lifespan, managing scheduled and recurring campaigns.
"""
import asyncio
import json
import logging
import os
from datetime import datetime

from core.domain.entities import (
    Campaign,
    CampaignStatus as DomainCampaignStatus,
)
from core.infrastructure.database.models import (
    CampaignModel,
    CampaignStatus as ModelCampaignStatus,
    InstanceModel,
)
from core.infrastructure.database.repositories import SQLCampaignRepository
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
        logger.error(
            "error in background campaign task for %s: %s", campaign_id, e, exc_info=True
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
        success = await humanized_sender.send_campaign_humanized(
            targets=campaign.target_groups,
            content=message,
            media_url=campaign.product.image_url,
        )
        campaign.status = (
            DomainCampaignStatus.SENT if success else DomainCampaignStatus.FAILED
        )
    except Exception as e:
        logger.error("error during humanized campaign send: %s", e, exc_info=True)
        campaign.status = DomainCampaignStatus.FAILED

    campaign.sent_at = datetime.utcnow()
    campaign_repo.save(campaign)
    logger.info(
        "campaign '%s' finished with status: %s", campaign.title, campaign.status.name
    )


async def campaign_scheduler_loop() -> None:
    """
    Background task that checks and dispatches scheduled/recurring campaigns every minute.
    """
    while True:
        db = SessionLocal()
        try:
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            current_day_str = now.strftime("%a").lower()

            # one-off campaigns
            one_off_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.status == ModelCampaignStatus.SCHEDULED,
                    ~CampaignModel.is_recurring,
                    CampaignModel.scheduled_at <= now,
                )
                .all()
            )

            for campaign_model in one_off_campaigns:
                logger.info(
                    "scheduling one-off campaign task: %s", campaign_model.title
                )
                campaign_model.status = ModelCampaignStatus.SENDING
                campaign_model.last_run_at = now
                db.add(campaign_model)
                db.commit()
                asyncio.create_task(execute_campaign_task(campaign_model.id))

            # recurring campaigns
            recurring_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.is_recurring,
                    CampaignModel.status != ModelCampaignStatus.FAILED,
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
                        campaign_model.status = ModelCampaignStatus.SENDING
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
                            campaign_model.status = ModelCampaignStatus.SENDING
                            campaign_model.last_run_at = now
                            db.add(campaign_model)
                            db.commit()
                            asyncio.create_task(execute_campaign_task(campaign_model.id))

        except Exception as e:
            logger.error("error in scheduler loop: %s", e, exc_info=True)
        finally:
            db.close()

        await asyncio.sleep(60)
