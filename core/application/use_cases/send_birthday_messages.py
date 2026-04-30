"""
use case: automated birthday message dispatch.
ported from the django cadastro module into fastapi clean architecture.
handles presence simulation, retry logic, and humanized delays.
"""

import asyncio
import logging
import random
from datetime import date

from sqlalchemy.orm import Session

from core.infrastructure.database.models import (
    BirthdayContactModel,
    BirthdayLogModel,
    BirthdayTemplateModel,
    InstanceModel,
)
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.infrastructure.utils.timezone import now_sp

logger = logging.getLogger(__name__)

MAX_RETRIES_PER_DAY = 5


class SendBirthdayMessages:
    """
    finds contacts whose birthday is today and sends
    the active birthday template via whatsapp.
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    async def execute(self) -> dict:
        today = now_sp().date()
        logger.info("[birthday] starting birthday dispatch for user %s on %s", self.user_id, today)

        # 1. get active template
        template = (
            self.db.query(BirthdayTemplateModel)
            .filter(
                BirthdayTemplateModel.user_id == self.user_id,
                BirthdayTemplateModel.is_enabled == True,  # noqa: E712
            )
            .first()
        )
        if not template:
            logger.warning("[birthday] no enabled template found for user %s", self.user_id)
            return {"sent": 0, "failed": 0, "skipped": 0, "error": "no active template"}

        # 2. find today's birthday contacts
        contacts = (
            self.db.query(BirthdayContactModel)
            .filter(
                BirthdayContactModel.user_id == self.user_id,
                BirthdayContactModel.is_active == True,  # noqa: E712
                BirthdayContactModel.birth_date.isnot(None),
            )
            .all()
        )

        birthday_contacts = [
            c for c in contacts
            if c.birth_date and c.birth_date.month == today.month and c.birth_date.day == today.day
        ]

        if not birthday_contacts:
            logger.info("[birthday] no birthday contacts today for user %s", self.user_id)
            return {"sent": 0, "failed": 0, "skipped": 0}

        logger.info("[birthday] found %d birthday contact(s)", len(birthday_contacts))

        # 3. get whatsapp instance
        instance = (
            self.db.query(InstanceModel)
            .filter(InstanceModel.user_id == self.user_id)
            .first()
        )
        if not instance:
            logger.error("[birthday] no whatsapp instance for user %s", self.user_id)
            return {"sent": 0, "failed": 0, "skipped": 0, "error": "no whatsapp instance"}

        whatsapp = EvolutionWhatsAppService(
            instance=instance.name,
            apikey=instance.apikey,
        )

        sent = 0
        failed = 0
        skipped = 0

        for i, contact in enumerate(birthday_contacts):
            result = await self._process_contact(contact, today, template, whatsapp)
            if result == "sent":
                sent += 1
            elif result == "failed":
                failed += 1
            else:
                skipped += 1

            # humanized jitter between sends
            if i < len(birthday_contacts) - 1:
                jitter = random.uniform(15, 60)
                logger.info("[birthday] waiting %.1fs before next send...", jitter)
                await asyncio.sleep(jitter)

        logger.info("[birthday] dispatch complete: sent=%d failed=%d skipped=%d", sent, failed, skipped)
        return {"sent": sent, "failed": failed, "skipped": skipped}

    async def _process_contact(
        self,
        contact: BirthdayContactModel,
        today: date,
        template: BirthdayTemplateModel,
        whatsapp: EvolutionWhatsAppService,
    ) -> str:
        if not contact.phone:
            logger.warning("[birthday] no phone for contact %s", contact.name)
            return "skipped"

        # check if already sent today
        already_sent = (
            self.db.query(BirthdayLogModel)
            .filter(
                BirthdayLogModel.contact_id == contact.id,
                BirthdayLogModel.status == "sent",
            )
            .all()
        )
        for log in already_sent:
            if log.sent_at and log.sent_at.date() == today:
                logger.info("[birthday] already sent today to %s", contact.name)
                return "skipped"

        # check retry cap
        fail_count = 0
        failed_logs = (
            self.db.query(BirthdayLogModel)
            .filter(
                BirthdayLogModel.contact_id == contact.id,
                BirthdayLogModel.status == "failed",
            )
            .all()
        )
        for log in failed_logs:
            if log.sent_at and log.sent_at.date() == today:
                fail_count += 1
        if fail_count >= MAX_RETRIES_PER_DAY:
            logger.warning("[birthday] max retries reached for %s", contact.name)
            return "skipped"

        # build personalized message
        first_name = contact.name.split()[0].title()
        content = template.content.replace("{nome}", first_name)

        # simulate typing presence
        try:
            presence_type = "recording" if template.media_url else "composing"
            typing_duration = random.uniform(3, 10)
            await whatsapp.set_presence(contact.phone, presence_type)
            await asyncio.sleep(typing_duration)
        except Exception as e:
            logger.warning("[birthday] presence simulation failed: %s", e)

        # send message
        success = False
        error_msg = None
        try:
            if template.media_url:
                success = await whatsapp.send_image(contact.phone, template.media_url, content)
            else:
                success = await whatsapp.send_text(contact.phone, content)
        except Exception as e:
            error_msg = str(e)
            logger.error("[birthday] send failed for %s: %s", contact.name, e)

        # log result
        log_entry = BirthdayLogModel(
            user_id=self.user_id,
            contact_id=contact.id,
            recipient_name=contact.name,
            recipient_phone=contact.phone,
            content=content,
            status="sent" if success else "failed",
            error_message=error_msg,
            sent_at=now_sp(),
        )
        self.db.add(log_entry)
        self.db.commit()

        if success:
            logger.info("[birthday] message sent to %s", contact.name)
            return "sent"
        else:
            logger.error("[birthday] failed to send to %s (attempt %d/%d)", contact.name, fail_count + 1, MAX_RETRIES_PER_DAY)
            return "failed"
