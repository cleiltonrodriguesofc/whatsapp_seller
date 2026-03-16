from core.application.interfaces import NotificationService
import logging

logger = logging.getLogger(__name__)


class SendDailyGreeting:
    """
    Use case to send a daily greeting message to a specific group or contact.
    """

    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    def execute(
        self, target: str, message: str = "Bom dia, pessoal! Como vocês estão?"
    ) -> bool:
        logger.info(f"Executing SendDailyGreeting for {target}")
        success = self.notification_service.send_text(target, message)
        if success:
            logger.info("Greeting sent successfully.")
        else:
            logger.error("Failed to send greeting.")
        return success
