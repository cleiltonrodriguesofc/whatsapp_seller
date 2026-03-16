from core.application.interfaces import NotificationService
import logging

logger = logging.getLogger(__name__)


class SalesAgentCampaignUseCase:
    """
    Direct use case to send a campaign message to a specific JID.
    Used primarily by external triggers (GitHub Actions, Webhooks).
    """

    def __init__(self, whatsapp_svc: NotificationService):
        self.whatsapp_svc = whatsapp_svc

    async def execute(self, target_jid: str, message: str) -> bool:
        if not target_jid:
            logger.error("Target JID is required for SalesAgentCampaignUseCase")
            return False

        logger.info(f"Executing SalesAgentCampaignUseCase for target: {target_jid}")
        return await self.whatsapp_svc.send_text(target_jid, message)
