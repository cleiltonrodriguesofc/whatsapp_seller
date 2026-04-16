import asyncio
import random
import logging
from core.infrastructure.utils.timezone import now_sp

from core.infrastructure.database.repositories import (
    SQLBroadcastCampaignRepository,
    SQLBroadcastListRepository,
    SQLTargetRepository,
)
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.infrastructure.utils.text_utils import parse_spintax
from core.infrastructure.utils.image_utils import get_optimized_base64

logger = logging.getLogger(__name__)


def _is_group_jid(jid: str) -> bool:
    """Returns True if the JID belongs to a group (ends with @g.us)."""
    return jid.endswith("@g.us")


class ExecuteBroadcastCampaignUseCase:
    def __init__(
        self,
        db_session,
        broadcast_repo: SQLBroadcastCampaignRepository,
        list_repo: SQLBroadcastListRepository,
        target_repo: SQLTargetRepository,
    ):
        self.db = db_session
        self.broadcast_repo = broadcast_repo
        self.list_repo = list_repo
        self.target_repo = target_repo

    async def execute(self, campaign_id: int):
        logger.info("[broadcast] starting campaign %s", campaign_id)
        campaign = self.broadcast_repo.get_by_id(
            campaign_id, user_id=None
        )  # user_id=None because scheduler runs as system
        if not campaign or campaign.status in ["sent", "failed"]:
            logger.warning(
                "[broadcast] campaign %s already done or not found, skipping",
                campaign_id,
            )
            return

        # 1. Update status to 'sending'
        campaign.status = "sending"
        self.broadcast_repo.save(campaign)

        # 2. Resolve target JIDs and names
        targets = []  # List of dict: {'jid': '...', 'name': '...'}

        if campaign.target_type == "list" and campaign.list_id:
            from core.infrastructure.database.models import BroadcastListMemberModel

            members = (
                self.list_repo.db.query(BroadcastListMemberModel)
                .filter_by(list_id=campaign.list_id)
                .all()
            )
            for m in members:
                targets.append({"jid": m.target_jid, "name": m.target_name})
        else:
            from core.infrastructure.database.models import WhatsAppTargetModel

            for jid in campaign.target_jids:
                target_model = (
                    self.target_repo.db.query(WhatsAppTargetModel)
                    .filter_by(user_id=campaign.user_id, jid=jid)
                    .first()
                )
                name = target_model.name if target_model else ""
                targets.append({"jid": jid, "name": name})

        campaign.total_targets = len(targets)
        self.broadcast_repo.save(campaign)
        logger.info("[broadcast] campaign %s has %d targets", campaign_id, len(targets))

        # 3. Setup WhatsApp Service
        from core.infrastructure.database.models import InstanceModel

        instance_model = self.db.query(InstanceModel).get(campaign.instance_id)
        if not instance_model:
            logger.error(
                "[broadcast] instance %s not found for campaign %s",
                campaign.instance_id,
                campaign_id,
            )
            campaign.status = "failed"
            self.broadcast_repo.save(campaign)
            return

        svc = EvolutionWhatsAppService(
            instance=instance_model.name, apikey=instance_model.apikey
        )

        # 4. Prepare Media
        # Use higher resolution for groups (images are shown bigger inside group chats)
        optimized_media = None
        if campaign.image_url:
            try:
                logger.info(
                    "[broadcast] downloading and optimizing image from: %s",
                    campaign.image_url[:80],
                )
                optimized_media = await get_optimized_base64(
                    campaign.image_url, max_size=(1000, 1000), quality=80
                )
                logger.info(
                    "[broadcast] image ready, size: %d chars (base64)",
                    len(optimized_media),
                )
            except Exception as e:
                logger.error(
                    "[broadcast] failed to prepare media: %s", e, exc_info=True
                )

        # 5. Send Loop (Humanized)
        sent_count = 0
        failed_count = 0

        for i, target in enumerate(targets):
            jid = target["jid"]
            full_name = target["name"] or ""
            is_group = _is_group_jid(jid)

            # Extract first name for personalization
            first_name = full_name.split(" ")[0] if full_name else ""

            # Personalization + Spintax
            content = campaign.message
            for placeholder in [
                "{nome}",
                "{{nome}}",
                "{nome_do_contato}",
                "{{nome_do_contato}}",
            ]:
                content = content.replace(placeholder, first_name)

            content = parse_spintax(content)

            logger.info(
                "[broadcast] sending to %s (%s) [%d/%d]",
                jid,
                "group" if is_group else "contact",
                i + 1,
                len(targets),
            )

            try:
                # Simulate typing only for direct contacts, NOT groups
                # Groups don't display per-contact typing indicators, and this adds 3-10s of delay per target
                if not is_group and jid != "status@broadcast":
                    typing_duration = random.uniform(2, 5)
                    logger.debug(
                        "[broadcast] simulating typing for %s (%.1fs)",
                        jid,
                        typing_duration,
                    )
                    await svc.set_presence(
                        jid, "composing", delay=int(typing_duration * 1000)
                    )
                    await asyncio.sleep(typing_duration)

                # Check for pause/cancel signal between sends
                try:
                    self.db.expire_all()
                    # reload to get latest status
                    current = self.db.query(type(campaign)).get(campaign.id)
                    if current and current.status in ["paused", "canceled"]:
                        logger.info(
                            "[broadcast] campaign %s is now %s, stopping loop at %d/%d",
                            campaign_id,
                            current.status,
                            i,
                            len(targets),
                        )
                        # just return, the loop is broken and state is already updated/saved in db by the trigger endpoint
                        return
                except Exception as e:
                    logger.warning("[broadcast] failed to check campaign status: %s", e)

                # Send message
                t_start = now_sp()
                success = False
                if optimized_media:
                    success = await svc.send_image(jid, optimized_media, content)
                else:
                    success = await svc.send_text(jid, content)

                elapsed = (now_sp() - t_start).total_seconds()
                logger.info(
                    "[broadcast] send to %s: %s (took %.2fs)",
                    jid,
                    "ok" if success else "FAILED",
                    elapsed,
                )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(
                    "[broadcast] error sending to %s: %s", jid, e, exc_info=True
                )
                failed_count += 1

            # Save progress
            campaign.sent_count = sent_count
            campaign.failed_count = failed_count
            self.broadcast_repo.save(campaign)

            # Humanized jitter delay between targets (only if there are more targets to send)
            if i < len(targets) - 1:
                jitter = random.uniform(
                    15, 60
                )  # reduced from 30-120s since groups don't need as much gap
                logger.info("[broadcast] waiting %.1fs before next target...", jitter)
                await asyncio.sleep(jitter)

        # 6. Final Status
        campaign.status = "sent" if sent_count > 0 else "failed"
        campaign.sent_at = now_sp()
        self.broadcast_repo.save(campaign)
        logger.info(
            "[broadcast] campaign %s finished: %d sent, %d failed",
            campaign_id,
            sent_count,
            failed_count,
        )
