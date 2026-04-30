"""
use case: dispatch affiliate product offers to whatsapp status.
fetches offers from marketplace gateways, generates ai-powered copy,
and posts them as status updates via evolution api.
"""

import logging

from core.application.interfaces import AffiliateGateway
from core.domain.entities import AffiliateOffer
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)

logger = logging.getLogger(__name__)


class DispatchStatusOffers:
    """
    fetches affiliate offers, generates marketing copy via ai,
    and posts them as whatsapp status updates.
    """

    def __init__(
        self,
        gateway: AffiliateGateway,
        whatsapp: EvolutionWhatsAppService,
        ai_service=None,
        min_discount: float = 20.0,
    ):
        self.gateway = gateway
        self.whatsapp = whatsapp
        self.ai_service = ai_service
        self.min_discount = min_discount

    async def execute(self, max_offers: int = 3) -> dict:
        logger.info("[affiliate] fetching offers with min discount %.0f%%", self.min_discount)

        try:
            offers = await self.gateway.get_offers(self.min_discount)
        except Exception as e:
            logger.error("[affiliate] failed to fetch offers: %s", e)
            return {"sent": 0, "failed": 0, "error": str(e)}

        if not offers:
            logger.info("[affiliate] no qualifying offers found")
            return {"sent": 0, "failed": 0}

        sent = 0
        failed = 0

        for offer in offers[:max_offers]:
            try:
                copy = await self._generate_copy(offer)

                if offer.image_url:
                    success = await self.whatsapp.send_status(
                        content=offer.image_url,
                        type="image",
                        caption=copy,
                    )
                else:
                    success = await self.whatsapp.send_status(
                        content=copy,
                        type="text",
                        backgroundColor="#000000",
                    )

                if success:
                    sent += 1
                    logger.info("[affiliate] status posted: %s", offer.title[:50])
                else:
                    failed += 1
                    logger.error("[affiliate] status send failed: %s", offer.title[:50])
            except Exception as e:
                failed += 1
                logger.error("[affiliate] error posting offer %s: %s", offer.title[:50], e)

        logger.info("[affiliate] dispatch complete: sent=%d failed=%d", sent, failed)
        return {"sent": sent, "failed": failed}

    async def _generate_copy(self, offer: AffiliateOffer) -> str:
        """generates marketing copy for a status post. uses ai if available, falls back to template."""
        if self.ai_service:
            try:
                prompt = (
                    f"Crie uma mensagem curta e animada para status do WhatsApp "
                    f"divulgando esta oferta:\n"
                    f"Produto: {offer.title}\n"
                    f"De R${offer.original_price:.2f} por R${offer.discount_price:.2f} "
                    f"({offer.discount_percent:.0f}% OFF)\n"
                    f"Link: {offer.affiliate_link}\n"
                    f"Use emojis. Máximo 3 linhas."
                )
                return await self.ai_service.chat(prompt)
            except Exception as e:
                logger.warning("[affiliate] ai copy generation failed, using fallback: %s", e)

        # fallback template
        return (
            f"🔥 OFERTA IMPERDÍVEL!\n"
            f"{offer.title}\n"
            f"De R${offer.original_price:.2f} por R${offer.discount_price:.2f} "
            f"({offer.discount_percent:.0f}% OFF)\n"
            f"👉 {offer.affiliate_link}"
        )
