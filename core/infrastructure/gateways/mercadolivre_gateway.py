"""
mercado livre affiliate gateway.
fetches product offers from the mercado livre api using the user's access token,
filters by minimum discount percentage, and generates affiliate links.
"""

import logging

import httpx

from core.application.interfaces import AffiliateGateway
from core.domain.entities import AffiliateOffer

logger = logging.getLogger(__name__)


class MercadoLivreGateway(AffiliateGateway):
    BASE_URL = "https://api.mercadolibre.com"

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def get_offers(self, min_discount_percent: float = 20.0) -> list[AffiliateOffer]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        timeout = httpx.Timeout(30.0, connect=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            # fetch user's affiliate catalog items
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/users/me/items/search",
                    headers=headers,
                    params={"status": "active"},
                )
                resp.raise_for_status()
                item_ids = resp.json().get("results", [])
            except Exception as e:
                logger.error("[ml-gateway] failed to fetch item list: %s", e)
                return []

            offers = []
            for item_id in item_ids[:10]:  # limit to prevent overload
                try:
                    item_resp = await client.get(
                        f"{self.BASE_URL}/items/{item_id}",
                        headers=headers,
                    )
                    item = item_resp.json()
                    original = item.get("original_price") or item.get("price")
                    current = item.get("price")

                    if not original or not current or original == current:
                        continue

                    discount = round((1 - current / original) * 100, 1)
                    if discount < min_discount_percent:
                        continue

                    # generate affiliate link
                    affiliate_link = item.get("permalink", "")
                    try:
                        aff_resp = await client.post(
                            f"{self.BASE_URL}/publisher/v2/links",
                            headers=headers,
                            json={"url": affiliate_link},
                        )
                        affiliate_link = aff_resp.json().get("url", affiliate_link)
                    except Exception as e:
                        logger.warning("[ml-gateway] affiliate link generation failed for %s: %s", item_id, e)

                    offers.append(AffiliateOffer(
                        title=item.get("title", ""),
                        original_price=original,
                        discount_price=current,
                        discount_percent=discount,
                        affiliate_link=affiliate_link,
                        image_url=item.get("thumbnail"),
                        source="mercadolivre",
                    ))
                except Exception as e:
                    logger.warning("[ml-gateway] error processing item %s: %s", item_id, e)
                    continue

            logger.info("[ml-gateway] found %d qualifying offers", len(offers))
            return offers
