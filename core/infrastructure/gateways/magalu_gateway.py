"""
magalu affiliate gateway.
fetches product offers from the user's magazine voce storefront
using playwright (headless browser) to bypass client-side rendering.
results are cached in memory to avoid excessive browser usage.
"""

import logging
import re
import json
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── category mapping for magalu ──────────────────────────────────
CATEGORY_MAP = {
    "notebook": {"path": "busca/notebook/", "label": "Notebooks"},
    "celular": {"path": "busca/celular/", "label": "Celulares"},
    "monitor": {"path": "busca/monitor/", "label": "Monitores"},
    "tablet": {"path": "busca/tablet/", "label": "Tablets"},
    "fone": {"path": "busca/fone+de+ouvido/", "label": "Fones de Ouvido"},
    "smart_tv": {"path": "busca/smart+tv/", "label": "Smart TVs"},
    "ssd": {"path": "busca/ssd/", "label": "SSDs"},
    "placa_video": {"path": "busca/placa+de+video/", "label": "Placas de Vídeo"},
    "teclado": {"path": "busca/teclado+gamer/", "label": "Teclados Gamer"},
    "mouse": {"path": "busca/mouse+gamer/", "label": "Mouses Gamer"},
    "impressora": {"path": "busca/impressora/", "label": "Impressoras"},
    "roteador": {"path": "busca/roteador/", "label": "Roteadores"},
    "console": {"path": "busca/console/", "label": "Consoles"},
}


@dataclass
class MagaluOffer:
    title: str
    price: float
    old_price: float | None
    discount_percent: float
    image_url: str
    affiliate_link: str
    category: str
    installment_text: str = ""
    pix_discount_text: str = ""


# ── in-memory cache ──────────────────────────────────────────────
_offer_cache: dict[str, dict] = {}  # key = storefront_slug, value = {expires, offers}
CACHE_TTL_HOURS = 4


class MagaluGateway:
    """fetches products from a magazine voce affiliate storefront."""

    BASE_URL = "https://www.magazinevoce.com.br"

    def __init__(self, storefront_slug: str):
        self.storefront_slug = storefront_slug
        self.store_url = f"{self.BASE_URL}/magazine{storefront_slug}"

    async def get_offers(
        self,
        categories: list[str],
        min_discount_percent: float = 10.0,
        max_offers: int = 5,
        preferred_brands: str = "",
    ) -> list[MagaluOffer]:
        """
        returns a list of product offers from the configured storefront.
        uses cache if available and not expired.
        """
        cache_key = self.storefront_slug
        now = datetime.utcnow()

        # check cache
        if cache_key in _offer_cache:
            cached = _offer_cache[cache_key]
            if cached["expires"] > now:
                logger.info("[magalu] serving %d offers from cache", len(cached["offers"]))
                filtered = [
                    o for o in cached["offers"]
                    if o.discount_percent >= min_discount_percent
                ]
                return filtered[:max_offers]

        # fetch fresh data
        all_offers = []
        brands = [b.strip() for b in preferred_brands.split(",") if b.strip()] if preferred_brands else []

        for cat_key in categories:
            cat = CATEGORY_MAP.get(cat_key)
            if not cat:
                logger.warning("[magalu] unknown category key: %s", cat_key)
                continue

            if brands:
                for brand in brands:
                    # use query string: magazinevoce.com.br/magazine{slug}/busca/{brand}+{category}/
                    search_term = f"{brand.replace(' ', '+')}+{cat_key}"
                    search_path = f"busca/{search_term}/"
                    label = f"{cat['label']} {brand}"
                    try:
                        offers = await self._fetch_category(search_path, label)
                        all_offers.extend(offers)
                    except Exception as e:
                        logger.error("[magalu] error fetching %s: %s", label, e)
            else:
                try:
                    offers = await self._fetch_category(cat["path"], cat["label"])
                    all_offers.extend(offers)
                except Exception as e:
                    logger.error("[magalu] error fetching category %s: %s", cat_key, e)

        # sort by discount descending
        all_offers.sort(key=lambda o: o.discount_percent, reverse=True)

        # update cache
        _offer_cache[cache_key] = {
            "expires": now + timedelta(hours=CACHE_TTL_HOURS),
            "offers": all_offers,
        }

        logger.info("[magalu] fetched %d total offers, caching for %dh", len(all_offers), CACHE_TTL_HOURS)

        filtered = [o for o in all_offers if o.discount_percent >= min_discount_percent]
        return filtered[:max_offers]

    def _fetch_category_sync(self, search_path: str, category_label: str) -> list[dict]:
        """uses sync playwright to browse a category and extract products to bypass asyncio issues on windows."""
        from playwright.sync_api import sync_playwright

        url = f"{self.store_url}/{search_path}"
        logger.info("[magalu] fetching %s", url)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-infobars",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu",
                        "--window-size=1366,768",
                        "--start-maximized",
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
                    bypass_csp=True,
                )
                
                # inject stealth scripts to remove automation fingerprints
                context.add_init_script("""
                    // remove webdriver property
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    
                    // spoof plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // spoof languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-BR', 'pt', 'en-US', 'en']
                    });
                    
                    // spoof permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // remove chrome automation indicators
                    window.chrome = { runtime: {} };
                    
                    // spoof platform
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32'
                    });
                """)
                
                page = context.new_page()

                # navigate and wait for product cards to render
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning("[magalu] page.goto timeout/error: %s. continuing anyway...", e)
                
                # simulate human-like scrolling to trigger lazy loading
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollBy(0, 400)")
                page.wait_for_timeout(1000)
                page.evaluate("window.scrollBy(0, 600)")
                page.wait_for_timeout(2000)

                # check if we hit a captcha page
                page_title = page.title() or ""
                page_content = page.content() or ""
                captcha_hit = (
                    "captcha" in page_title.lower()
                    or "captcha" in page_content.lower()
                    or "robot" in page_content.lower()
                    or "challenge" in page_content.lower()
                )
                if captcha_hit:
                    logger.warning("[magalu] captcha detected on %s, trying to wait longer...", url)
                    page.wait_for_timeout(6000)
                    page.evaluate("window.scrollBy(0, 300)")
                    page.wait_for_timeout(2000)

                # extract product data from the rendered page
                products = page.evaluate("""
                    () => {
                        const items = [];
                        const seen = new Set();

                        const links = document.querySelectorAll('a[href*="/p/"]');

                        for (const link of links) {
                            try {
                                const href = link.href || '';
                                const pidMatch = href.match(/\\/p\\/([^/?]+)/);
                                const pid = pidMatch ? pidMatch[1] : href;
                                if (seen.has(pid)) continue;
                                seen.add(pid);

                                const allText = card_text(link);

                                // extract title: everything before the first rating pattern or R$
                                let title = allText
                                    .replace(/\\d+[.,]\\d+\\s*\\(\\d+\\)/g, '')  // remove "4.8 (379)"
                                    .split(/R\\$/)[0]                          // cut before first R$
                                    .replace(/^Full/, '')                     // remove leading "Full"
                                    .trim();
                                // cap at 100 chars
                                if (title.length > 100) title = title.substring(0, 100) + '...';

                                // attempt to find prices via data attributes first
                                let oldPriceEl = link.querySelector('[data-testid="price-original"]') || 
                                                 link.querySelector('[data-testid="price-list"]') ||
                                                 link.querySelector('.price-original');
                                
                                let currentPriceEl = link.querySelector('[data-testid="price-value"]') ||
                                                     link.querySelector('[data-testid="price-current"]') ||
                                                     link.querySelector('.price-value');
                                
                                let oldPriceText = oldPriceEl ? oldPriceEl.textContent : '';
                                let priceText = currentPriceEl ? currentPriceEl.textContent : '';

                                // if data-testids fail, fallback to text parsing
                                if (!priceText || !oldPriceText) {
                                    // extract ALL R$ values from text
                                    const priceRegex = /R\\\$\\s*([\\d.,]+)/g;
                                    const priceValues = [];
                                    let m;
                                    while ((m = priceRegex.exec(allText)) !== null) {
                                        priceValues.push(m[0]);
                                    }

                                    if (!priceText && priceValues.length > 0) {
                                        // usually the last one is the best price (pix or cash)
                                        priceText = priceValues[priceValues.length - 1];
                                    }

                                    if (!oldPriceText && priceValues.length > 1) {
                                        // look for "De: R$" specifically
                                        const deMatch = allText.match(/De:\s*(R\$\s*[\d.,]+)/i);
                                        if (deMatch) {
                                            oldPriceText = deMatch[1];
                                        } else {
                                            // fallback to first price found
                                            oldPriceText = priceValues[0];
                                        }
                                    }
                                }

                                // installment and pix discount
                                let installmentEl = link.querySelector('[data-testid="installment"]');
                                let installmentText = installmentEl ? installmentEl.textContent : '';
                                if (!installmentText) {
                                    const instMatch = allText.match(/(\\d+x\\s+de\\s+R\\$\\s*[\\d.,]+\\s+sem\\s+juros)/i);
                                    if (instMatch) installmentText = instMatch[1];
                                }

                                const pixDiscMatch = allText.match(/\\((\\d+% de desconto no pix)\\)/i) || allText.match(/\\((.*desconto.*)\\)/i);
                                let pixDiscountText = pixDiscMatch ? pixDiscMatch[1] : '';

                                // image
                                const imgEl = link.querySelector('img');
                                const imgSrc = imgEl?.src || imgEl?.getAttribute('data-src') || '';

                                if (title && href && priceText) {
                                    items.push({
                                        title: title,
                                        price: priceText,
                                        oldPrice: oldPriceText,
                                        image: imgSrc,
                                        link: href,
                                        installment: installmentText,
                                        pixDiscount: pixDiscountText
                                    });
                                }
                            } catch(e) { /* skip */ }
                        }
                        return items.slice(0, 20);

                        function card_text(el) {
                            return (el.textContent || '').replace(/\\s+/g, ' ').trim();
                        }
                    }
                """)

                browser.close()
                return products

        except Exception as e:
            logger.error("[magalu] playwright error: %s", e)
            return []

    async def _fetch_category(self, search_path: str, category_label: str) -> list[MagaluOffer]:
        """uses playwright to browse a category and extract products."""
        products = await asyncio.to_thread(self._fetch_category_sync, search_path, category_label)
        
        offers = []
        # parse and build offer objects
        for item in products:
            try:
                price = self._parse_price(item.get("price", ""))
                old_price = self._parse_price(item.get("oldPrice", ""))

                if not price or price <= 0:
                    continue

                # calculate discount
                discount = 0.0
                if old_price and old_price > price:
                    discount = round((1 - price / old_price) * 100, 1)

                # ensure the link is an affiliate link (through the storefront)
                link = item.get("link", "")
                if "magazinevoce.com.br" not in link and "magazineluiza.com.br" in link:
                    # convert to affiliate link
                    link = link.replace(
                        "www.magazineluiza.com.br",
                        f"www.magazinevoce.com.br/magazine{self.storefront_slug}"
                    )

                offers.append(MagaluOffer(
                    title=item.get("title", "Oferta Magalu"),
                    price=price,
                    old_price=old_price,
                    discount_percent=discount,
                    image_url=item.get("image", ""),
                    affiliate_link=link,
                    category=category_label,
                    installment_text=item.get("installment", ""),
                    pix_discount_text=item.get("pixDiscount", ""),
                ))
            except Exception as e:
                logger.warning("[magalu] error parsing product: %s", e)

        logger.info("[magalu] parsed %d offers from category %s", len(offers), category_label)
        return offers

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """parses a brazilian price string like 'R$ 2.399,90' into float."""
        if not text:
            return None
        # remove everything except digits, comma and dot
        cleaned = re.sub(r"[^\d,.]", "", text.strip())
        if not cleaned:
            return None
        # handle brazilian format: 2.399,90 -> 2399.90
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
        """returns available category keys and their labels."""
        return {k: v["label"] for k, v in CATEGORY_MAP.items()}
