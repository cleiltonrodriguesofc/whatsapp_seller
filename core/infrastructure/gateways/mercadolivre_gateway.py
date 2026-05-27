"""
mercado livre affiliate gateway.
fetches product offers from the user's mercado livre social affiliate profile
using playwright (headless browser) to bypass client-side rendering.
links from the profile page are already affiliate-tracked by mercado livre.
results are cached in memory to avoid excessive browser usage.
"""

import logging
import re
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── category search terms for ml electronics ─────────────────────────────
ML_CATEGORY_MAP = {
    "notebook": {"query": "notebook", "label": "Notebooks"},
    "celular": {"query": "celular smartphone", "label": "Celulares"},
    "tablet": {"query": "tablet", "label": "Tablets"},
    "smart_tv": {"query": "smart tv", "label": "Smart TVs"},
    "fone": {"query": "fone de ouvido bluetooth", "label": "Fones de Ouvido"},
    "ssd": {"query": "ssd interno nvme", "label": "SSDs"},
    "placa_video": {"query": "placa de video nvidia", "label": "Placas de Vídeo"},
    "console": {"query": "console playstation xbox", "label": "Consoles"},
    "monitor": {"query": "monitor gamer", "label": "Monitores"},
    "mouse": {"query": "mouse gamer sem fio", "label": "Mouses Gamer"},
    "teclado": {"query": "teclado gamer mecanico", "label": "Teclados Gamer"},
    "impressora": {"query": "impressora multifuncional", "label": "Impressoras"},
}

BASE_ML_URL = "https://www.mercadolivre.com.br"


@dataclass
class MLOffer:
    title: str
    price: float
    old_price: float | None
    discount_percent: float
    image_url: str
    affiliate_link: str
    category: str
    installment_text: str = ""


# ── in-memory cache ───────────────────────────────────────────────────────
_ml_cache: dict[str, dict] = {}
CACHE_TTL_HOURS = 4


class MercadoLivreGateway:
    """
    fetches electronics products from the user's ml social affiliate profile.
    the profile url format is: mercadolivre.com.br/social/{profile_slug}/lists
    all links extracted from the profile are already affiliate-tracked.
    """

    def __init__(self, profile_slug: str):
        """
        profile_slug: the username portion of the ml social url.
        e.g. for mercadolivre.com.br/social/cleiltonrodriguesdossantos
        pass 'cleiltonrodriguesdossantos'.
        """
        self.profile_slug = profile_slug
        self.profile_url = f"{BASE_ML_URL}/social/{profile_slug}/lists"

    async def get_offers(
        self,
        categories: list[str] | None = None,
        min_discount_percent: float = 5.0,
        max_offers: int = 5,
    ) -> list[MLOffer]:
        """
        returns affiliate offers from the ml social profile.
        uses cache if available and not expired.
        """
        cache_key = self.profile_slug
        now = datetime.utcnow()

        if cache_key in _ml_cache:
            cached = _ml_cache[cache_key]
            if cached["expires"] > now:
                logger.info("[ml] serving %d offers from cache", len(cached["offers"]))
                filtered = [
                    o for o in cached["offers"]
                    if o.discount_percent >= min_discount_percent
                ]
                return filtered[:max_offers]

        # fetch fresh data from the profile page
        all_offers = await asyncio.to_thread(self._scrape_profile_sync)

        # update cache
        _ml_cache[cache_key] = {
            "expires": now + timedelta(hours=CACHE_TTL_HOURS),
            "offers": all_offers,
        }

        logger.info("[ml] scraped %d total offers from profile, caching for %dh", len(all_offers), CACHE_TTL_HOURS)

        filtered = [o for o in all_offers if o.discount_percent >= min_discount_percent]
        return filtered[:max_offers]

    def _scrape_profile_sync(self) -> list["MLOffer"]:
        """
        uses sync playwright to scrape the ml social profile page.
        all product links on the page are already affiliate-tracked by ml.
        """
        from playwright.sync_api import sync_playwright

        logger.info("[ml] scraping profile: %s", self.profile_url)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--window-size=1366,768",
                    ],
                )
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1366, "height": 768},
                    locale="pt-BR",
                    java_script_enabled=True,
                )

                # stealth: remove webdriver fingerprint
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en'] });
                    window.chrome = { runtime: {} };
                """)

                page = context.new_page()

                try:
                    page.goto(self.profile_url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning("[ml] goto timeout/error: %s. continuing anyway...", e)

                # scroll to trigger lazy-loaded product cards
                page.wait_for_timeout(3000)
                page.evaluate("window.scrollBy(0, 500)")
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

                raw_products = page.evaluate("""
                    () => {
                        const items = [];
                        const seen = new Set();

                        // ml social profile renders product cards with links to items
                        // try multiple selectors that ml uses for product cards
                        let links = [];
                        const selectors = [
                            'a[href*="produto.mercadolivre"]',
                            'a[href*="mercadolivre.com.br/p/"]',
                            'a[href*="mercadolivre.com.br/MLB"]',
                        ];

                        for (const sel of selectors) {
                            const found = document.querySelectorAll(sel);
                            if (found.length > 0) {
                                links = [...found];
                                break;
                            }
                        }

                        // fallback: all links matching ml product url patterns
                        if (links.length === 0) {
                            links = Array.from(document.querySelectorAll('a[href]')).filter(a => {
                                const h = a.href || '';
                                return (h.includes('mercadolivre.com.br') || h.includes('produto.mercadolivre')) &&
                                       (h.includes('/p/') || h.includes('/MLB') || h.includes('-MLB'));
                            });
                        }

                        for (const link of links) {
                            try {
                                const href = link.href || '';
                                if (!href || seen.has(href)) continue;
                                seen.add(href);

                                const allText = (link.textContent || '').replace(/\\s+/g, ' ').trim();
                                if (!allText) continue;

                                // extract title: text before the first price (R$)
                                let title = allText.split(/R\\$/)[0].trim();
                                title = title.replace(/\\d+[.,]\\d+\\s*\\(\\d+\\)/g, '').trim();
                                if (!title || title.length < 5) continue;
                                if (title.length > 120) title = title.substring(0, 120) + '...';

                                // find all price occurrences
                                const priceRegex = /R\\$\\s*([\\d.,]+)/g;
                                const prices = [];
                                let m;
                                while ((m = priceRegex.exec(allText)) !== null) {
                                    prices.push(m[0]);
                                }

                                // last price = current (pix/cash), first = original
                                const priceText = prices.length > 0 ? prices[prices.length - 1] : '';
                                const oldPriceText = prices.length > 1 ? prices[0] : '';

                                if (!priceText) continue;

                                // image
                                const img = link.querySelector('img');
                                const imgSrc = img?.src || img?.getAttribute('data-src') || '';

                                // installments
                                const instMatch = allText.match(/(\\d+x\\s+(?:de\\s+)?R\\$\\s*[\\d.,]+(?:\\s+sem\\s+juros)?)/i);
                                const installmentText = instMatch ? instMatch[1] : '';

                                // explicit discount text
                                const discMatch = allText.match(/(\\d+)%\\s*(?:OFF|de\\s+desconto)/i);
                                const discText = discMatch ? discMatch[0] : '';

                                items.push({
                                    title: title,
                                    price: priceText,
                                    oldPrice: oldPriceText,
                                    image: imgSrc,
                                    link: href,
                                    installment: installmentText,
                                    discountText: discText,
                                });
                            } catch(e) { /* skip */ }
                        }

                        return items.slice(0, 30);
                    }
                """)

                browser.close()
                logger.info("[ml] extracted %d raw products from profile page", len(raw_products))
                return self._parse_products(raw_products)

        except Exception as e:
            logger.error("[ml] playwright error scraping profile: %s", e)
            return []

    def _parse_products(self, raw_products: list[dict]) -> list["MLOffer"]:
        """parses raw scraped product dicts into MLOffer objects."""
        offers = []
        for item in raw_products:
            try:
                price = self._parse_price(item.get("price", ""))
                old_price = self._parse_price(item.get("oldPrice", ""))

                if not price or price <= 0:
                    continue

                discount = 0.0
                if old_price and old_price > price:
                    discount = round((1 - price / old_price) * 100, 1)

                # extract discount from text if no price-based discount
                if discount == 0 and item.get("discountText"):
                    m = re.search(r"(\d+)%", item["discountText"])
                    if m:
                        discount = float(m.group(1))

                offers.append(MLOffer(
                    title=item.get("title", "Oferta ML"),
                    price=price,
                    old_price=old_price,
                    discount_percent=discount,
                    image_url=item.get("image", ""),
                    affiliate_link=item.get("link", ""),
                    category="eletrônicos",
                    installment_text=item.get("installment", ""),
                ))
            except Exception as e:
                logger.warning("[ml] error parsing product: %s", e)

        # sort by discount descending
        offers.sort(key=lambda o: o.discount_percent, reverse=True)
        logger.info("[ml] parsed %d valid offers from profile", len(offers))
        return offers

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """parses a brazilian price string like 'R$ 2.399,90' into float."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d,.]", "", text.strip())
        if not cleaned:
            return None
        if "," in cleaned:
            parts = cleaned.rsplit(",", 1)
            integer_part = parts[0].replace(".", "")
            decimal_part = parts[1] if len(parts) > 1 else "00"
            cleaned = f"{integer_part}.{decimal_part}"
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def get_available_categories() -> dict[str, str]:
        """returns available category keys and labels."""
        return {k: v["label"] for k, v in ML_CATEGORY_MAP.items()}
