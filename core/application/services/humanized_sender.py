import asyncio
import random
import logging
from typing import List, Optional
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.domain.entities import Campaign

logger = logging.getLogger(__name__)


class HumanizedSender:
    """
    Handles sending messages to multiple targets with human-like behavior:
    1. Randomized delays (jitter) between targets.
    2. "Typing..." or "Recording..." presence simulation.
    3. Respecting rate limits.
    """

    def __init__(self, whatsapp_service: EvolutionWhatsAppService):
        self.svc = whatsapp_service
        self.min_delay = 30  # seconds
        self.max_delay = 120  # seconds

    async def send_campaign_humanized(
        self, targets: List[str], content: str, media_url: Optional[str] = None
    ):
        """
        Sends a message to a list of targets with human-like delays.
        """
        from core.infrastructure.utils.image_utils import get_optimized_base64

        optimized_media = None
        if media_url:
            try:
                optimized_media = await get_optimized_base64(media_url)
                logger.info("Media optimized for humanized send.")
            except Exception as e:
                logger.error("Failed to optimize media for humanized send: %s", e)

        for i, target in enumerate(targets):
            # 1. Simulate Typing/Presence (only if not sending to status)
            if target != "status@broadcast":
                try:
                    # We set a random typing duration between 3 and 10 seconds
                    typing_duration = random.uniform(3, 10)
                    await self.svc.set_presence(
                        target, "composing", delay=int(typing_duration * 1000)
                    )
                    await asyncio.sleep(typing_duration)
                except Exception as e:
                    logger.warning("Failed to set presence for %s: %s", target, e)

            # 2. Send the message
            success = False
            if optimized_media:
                success = await self.svc.send_image(target, optimized_media, content)
            else:
                success = await self.svc.send_text(target, content)

            if success:
                logger.info(
                    "Humanized send successful to %s (%d/%d)",
                    target,
                    i + 1,
                    len(targets),
                )
            else:
                logger.error("Humanized send failed to %s", target)

            # 3. Random Jitter Delay (except for the last target)
            if i < len(targets) - 1:
                jitter = random.uniform(self.min_delay, self.max_delay)
                logger.info(
                    "Humanized delay: waiting %.2f seconds before next target...",
                    jitter,
                )
                await asyncio.sleep(jitter)

        return True
