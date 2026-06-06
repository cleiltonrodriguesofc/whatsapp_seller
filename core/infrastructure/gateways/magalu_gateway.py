"""
magalu affiliate gateway.
fetches product offers from the user's magazine voce storefront
using two strategies:
1. http scraping with googlebot UA (primary) — fast, no browser needed
2. fallback to magazineluiza.com.br search page scraping

results are cached in memory to avoid excessive requests.
"""

import logging
import re
import json
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── category mapping for magalu ──────────────────────────────────
CATEGORY_MAP = {
    # Eletrônicos & Informática
    "notebook": {"path": "busca/notebook/", "query": "notebook", "label": "Notebooks"},
    "celular": {"path": "busca/celular/", "query": "celular smartphone", "label": "Celulares"},
    "monitor": {"path": "busca/monitor/", "query": "monitor gamer", "label": "Monitores"},
    "tablet": {"path": "busca/tablet/", "query": "tablet", "label": "Tablets"},
    "fone": {"path": "busca/fone+de+ouvido/", "query": "fone bluetooth", "label": "Fones de Ouvido"},
    "smart_tv": {"path": "busca/smart+tv/", "query": "smart tv 4k", "label": "Smart TVs"},
    "ssd": {"path": "busca/ssd/", "query": "ssd nvme", "label": "SSDs"},
    "placa_video": {"path": "busca/placa+de+video/", "query": "placa de video nvidia", "label": "Placas de Vídeo"},
    "teclado": {"path": "busca/teclado+gamer/", "query": "teclado gamer mecanico", "label": "Teclados Gamer"},
    "mouse": {"path": "busca/mouse+gamer/", "query": "mouse gamer", "label": "Mouses Gamer"},
    "impressora": {"path": "busca/impressora/", "query": "impressora multifuncional", "label": "Impressoras"},
    "roteador": {"path": "busca/roteador/", "query": "roteador wifi", "label": "Roteadores"},
    "console": {"path": "busca/console/", "query": "console playstation xbox", "label": "Consoles"},
    # Eletrodomésticos
    "ar_condicionado": {"path": "busca/ar+condicionado/", "query": "ar condicionado split", "label": "Ar Condicionado"},
    "geladeira": {"path": "busca/geladeira/", "query": "geladeira frost free", "label": "Geladeiras"},
    "maquina_lavar": {"path": "busca/maquina+de+lavar/", "query": "maquina de lavar", "label": "Máquinas de Lavar"},
    "fogao": {"path": "busca/fogao/", "query": "fogao 5 bocas", "label": "Fogões"},
    "microondas": {"path": "busca/microondas/", "query": "microondas", "label": "Microondas"},
    "fritadeira": {"path": "busca/air+fryer/", "query": "air fryer fritadeira", "label": "Fritadeiras Air Fryer"},
    "ventilador": {"path": "busca/ventilador/", "query": "ventilador", "label": "Ventiladores"},
    "liquidificador": {"path": "busca/liquidificador/", "query": "liquidificador", "label": "Liquidificadores"},
    "batedeira": {"path": "busca/batedeira/", "query": "batedeira planetaria", "label": "Batedeiras"},
    # Beleza & Cuidado Pessoal
    "secador_cabelo": {"path": "busca/secador+de+cabelo/", "query": "secador de cabelo profissional", "label": "Secadores de Cabelo"},
    "chapinha": {"path": "busca/chapinha/", "query": "chapinha prancha", "label": "Chapinhas"},
    "barbeador": {"path": "busca/barbeador/", "query": "barbeador eletrico", "label": "Barbeadores Elétricos"},
    "perfume": {"path": "busca/perfume/", "query": "perfume importado", "label": "Perfumes Importados"},
    # Casa & Jardim
    "aspirador": {"path": "busca/aspirador+robo/", "query": "aspirador robo", "label": "Aspiradores Robô"},
    "furadeira": {"path": "busca/furadeira/", "query": "furadeira parafusadeira", "label": "Ferramentas Elétricas"},
    # Esporte & Lazer
    "bicicleta": {"path": "busca/bicicleta/", "query": "bicicleta aro 29", "label": "Bicicletas"},
    "tenis_corrida": {"path": "busca/tenis+corrida/", "query": "tenis corrida", "label": "Tênis Esportivos"},
    # Bebês & Moda
    "carrinho_bebe": {"path": "busca/carrinho+de+bebe/", "query": "carrinho de bebe", "label": "Carrinhos de Bebê"},
    "fralda": {"path": "busca/fralda/", "query": "fralda pampers", "label": "Fraldas"},
}


@dataclass
class MagaluOffer:
    """Represents a single product offer from Magalu."""
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
    """Fetches products from a Magazine Voce affiliate storefront."""

    BASE_URL = "https://www.magazinevoce.com.br"
    MAGALU_SEARCH_URL = "https://www.magazineluiza.com.br"

    def __init__(self, storefront_slug: str):
        self.storefront_slug = storefront_slug
        self.store_url = f"{self.BASE_URL}/magazine{storefront_slug}"

    async def get_offers(
        self,
        categories: list[str],
        min_discount_percent: float = 10.0,
        max_offers: int = 5,
        preferred_brands: str = "",
        custom_search_terms: str = "",
    ) -> list[MagaluOffer]:
        """
        Returns a list of product offers from the configured storefront.
        Uses cache if available and not expired.
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

        search_terms = []
        if custom_search_terms:
            terms = [t.strip() for t in custom_search_terms.split(",") if t.strip()]
            for term in terms:
                search_terms.append((term, term))
        else:
            for cat_key in categories:
                cat = CATEGORY_MAP.get(cat_key)
                if not cat:
                    continue
                if brands:
                    for brand in brands:
                        search_terms.append((f"{cat['query']} {brand}", f"{cat['label']} {brand}"))
                else:
                    search_terms.append((cat["query"], cat["label"]))

        if not search_terms:
            return []

        # fetch all categories concurrently
        tasks = [
            self._fetch_category(query, label)
            for query, label in search_terms
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_offers.extend(result)
            elif isinstance(result, Exception):
                logger.warning("[magalu] category fetch error: %s", result)

        # sort by discount descending, deduplicate by title
        all_offers.sort(key=lambda o: o.discount_percent, reverse=True)
        seen_titles: set[str] = set()
        unique_offers: list[MagaluOffer] = []
        for o in all_offers:
            if brands and not any(b.lower() in o.title.lower() for b in brands):
                continue
            key = o.title[:50].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                unique_offers.append(o)

        # ONLY cache if we got results — never cache empty results
        if unique_offers:
            _offer_cache[cache_key] = {
                "expires": now + timedelta(hours=CACHE_TTL_HOURS),
                "offers": unique_offers,
            }

        logger.info("[magalu] fetched %d total offers, caching for %dh", len(unique_offers), CACHE_TTL_HOURS if unique_offers else 0)

        filtered = [o for o in unique_offers if o.discount_percent >= min_discount_percent]
        return filtered[:max_offers]

    async def _fetch_category(self, search_query: str, category_label: str) -> list[MagaluOffer]:
        """Fetches products. Tries HTTP scraping of magazineluiza.com.br first."""
        # Strategy 1: scrape magazineluiza.com.br search page (fast, no Playwright needed)
        offers = await self._fetch_via_http_scrape(search_query, category_label)
        if offers:
            return offers

        # Strategy 2: try the storefront page directly
        logger.info("[magalu] primary scrape returned nothing for '%s', trying storefront", search_query)
        return await self._fetch_via_storefront_scrape(search_query, category_label)

    # ── strategy 1: HTTP scraping of magazineluiza.com.br ─────────────
    async def _fetch_via_http_scrape(self, search_query: str, category_label: str) -> list[MagaluOffer]:
        """Scrapes magazineluiza.com.br search results using Googlebot UA to get server-rendered HTML."""
        search_slug = search_query.replace(" ", "+")
        url = f"{self.MAGALU_SEARCH_URL}/busca/{search_slug}/"

        # Use Googlebot UA to bypass login/captcha walls and get SSR content
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Cache-Control": "no-cache",
        }

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.error("[magalu] HTTP scrape fetch error for '%s': %s", search_query, e)
            return []

        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1a: try to find product data in JSON-LD structured data
        offers = self._parse_json_ld(soup, category_label)
        if offers:
            logger.info("[magalu] parsed %d offers from JSON-LD for '%s'", len(offers), search_query)
            return offers

        # Strategy 1b: try to parse from __NEXT_DATA__ script tag
        offers = self._parse_next_data(soup, category_label)
        if offers:
            logger.info("[magalu] parsed %d offers from __NEXT_DATA__ for '%s'", len(offers), search_query)
            return offers

        # Strategy 1c: parse from HTML product cards
        offers = self._parse_html_cards(soup, category_label)
        if offers:
            logger.info("[magalu] parsed %d offers from HTML cards for '%s'", len(offers), search_query)
            return offers

        logger.warning("[magalu] no products found via HTTP scrape for '%s' (page len=%d)", search_query, len(html))
        return []

    def _parse_json_ld(self, soup: BeautifulSoup, category_label: str) -> list[MagaluOffer]:
        """Tries to parse product data from JSON-LD script tags."""
        offers = []
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                items = []
                if isinstance(data, dict):
                    if data.get("@type") == "ItemList":
                        items = data.get("itemListElement", [])
                    elif data.get("@type") == "Product":
                        items = [data]
                elif isinstance(data, list):
                    items = data

                for item in items:
                    product = item.get("item", item) if "item" in item else item
                    if product.get("@type") != "Product":
                        continue

                    title = product.get("name", "").strip()
                    if not title or len(title) < 5:
                        continue

                    offers_data = product.get("offers", {})
                    if isinstance(offers_data, list):
                        offers_data = offers_data[0] if offers_data else {}

                    price = float(offers_data.get("price", 0) or 0)
                    if price <= 0:
                        continue

                    product_url = product.get("url", "")
                    image_url = product.get("image", "")
                    if isinstance(image_url, list):
                        image_url = image_url[0] if image_url else ""

                    affiliate_link = self._convert_to_affiliate_link(product_url)

                    if len(title) > 100:
                        title = title[:97] + "..."

                    offers.append(MagaluOffer(
                        title=title,
                        price=price,
                        old_price=None,
                        discount_percent=0.0,
                        image_url=image_url,
                        affiliate_link=affiliate_link,
                        category=category_label,
                    ))
            except Exception as e:
                logger.debug("[magalu] JSON-LD parse error: %s", e)

        return offers[:20]

    def _parse_next_data(self, soup: BeautifulSoup, category_label: str) -> list[MagaluOffer]:
        """Tries to parse product data from a __NEXT_DATA__ script tag."""
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script or not script.string:
            return []

        try:
            data = json.loads(script.string)
            # Traverse the Next.js page props to find product results
            page_props = data.get("props", {}).get("pageProps", {})

            # common patterns for Next.js search results
            products = (
                page_props.get("results", [])
                or page_props.get("products", [])
                or page_props.get("data", {}).get("search", {}).get("products", [])
            )

            if not products:
                # deep search for arrays that look like product lists
                return self._deep_search_products(page_props, category_label)

            offers = []
            for item in products[:20]:
                offer = self._parse_next_product(item, category_label)
                if offer:
                    offers.append(offer)
            return offers

        except Exception as e:
            logger.debug("[magalu] __NEXT_DATA__ parse error: %s", e)
            return []

    def _deep_search_products(self, data: dict, category_label: str, depth: int = 0) -> list[MagaluOffer]:
        """Recursively searches for product arrays in nested JSON data."""
        if depth > 5:
            return []

        offers = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 2:
                    # Check if items look like products
                    sample = value[0] if value else {}
                    if isinstance(sample, dict) and any(
                        k in sample for k in ["title", "name", "price", "priceInfo", "product"]
                    ):
                        for item in value[:20]:
                            offer = self._parse_next_product(item, category_label)
                            if offer:
                                offers.append(offer)
                        if offers:
                            return offers
                elif isinstance(value, dict):
                    result = self._deep_search_products(value, category_label, depth + 1)
                    if result:
                        return result
        return offers

    def _parse_next_product(self, item: dict, category_label: str) -> MagaluOffer | None:
        """Parses a single product from __NEXT_DATA__ JSON."""
        try:
            title = (
                item.get("title")
                or item.get("name")
                or item.get("product", {}).get("title", "")
            ).strip()

            if not title or len(title) < 5:
                return None

            # price extraction — handle various structures
            price_info = item.get("priceInfo", item.get("price", {}))
            if isinstance(price_info, dict):
                price = float(price_info.get("bestPrice", 0) or price_info.get("price", 0) or 0)
                old_price = float(price_info.get("listPrice", 0) or price_info.get("oldPrice", 0) or 0)
            elif isinstance(price_info, (int, float)):
                price = float(price_info)
                old_price = float(item.get("oldPrice", 0) or item.get("listPrice", 0) or 0)
            else:
                price = float(item.get("price", 0) or 0)
                old_price = float(item.get("oldPrice", 0) or item.get("original_price", 0) or 0)

            if price <= 0:
                return None

            discount = 0.0
            if old_price and old_price > price:
                discount = round((1 - price / old_price) * 100, 1)

            # image
            image_url = (
                item.get("image")
                or item.get("imageUrl")
                or item.get("thumbnail", "")
            )
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else ""

            # link
            product_url = item.get("url") or item.get("link") or item.get("permalink", "")
            if product_url and not product_url.startswith("http"):
                product_url = f"https://www.magazineluiza.com.br{product_url}"

            affiliate_link = self._convert_to_affiliate_link(product_url)

            # installment
            installment_text = ""
            installments = item.get("installment") or item.get("installments")
            if isinstance(installments, dict):
                qty = installments.get("quantity") or installments.get("totalNumber")
                amount = installments.get("amount") or installments.get("value")
                if qty and amount:
                    price_fmt = f"R$ {float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    installment_text = f"{qty}x de {price_fmt}"

            if len(title) > 100:
                title = title[:97] + "..."

            return MagaluOffer(
                title=title,
                price=price,
                old_price=old_price if old_price > price else None,
                discount_percent=discount,
                image_url=image_url,
                affiliate_link=affiliate_link,
                category=category_label,
                installment_text=installment_text,
            )
        except Exception as e:
            logger.debug("[magalu] error parsing __NEXT_DATA__ product: %s", e)
            return None

    def _parse_html_cards(self, soup: BeautifulSoup, category_label: str) -> list[MagaluOffer]:
        """Parses product data from HTML product card elements."""
        offers = []

        # try multiple known selectors for Magalu product cards
        selectors = [
            "li[data-testid='product-card']",
            "a[data-testid='product-card-container']",
            ".product-card",
            "a[href*='/p/']",
            ".sc-fKFyDc",  # styled-component based cards
        ]

        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                break

        if not items:
            # Broad fallback: find all links to /p/ (product pages)
            items = soup.find_all("a", href=re.compile(r"/p/"))
            # deduplicate by href
            seen_hrefs = set()
            unique_items = []
            for item in items:
                href = item.get("href", "")
                pid_match = re.search(r"/p/([^/?]+)", href)
                pid = pid_match.group(1) if pid_match else href
                if pid not in seen_hrefs:
                    seen_hrefs.add(pid)
                    unique_items.append(item)
            items = unique_items

        for item in items[:20]:
            try:
                # get the full text content for price/title extraction
                all_text = " ".join(item.stripped_strings)

                # title
                title_node = (
                    item.select_one("h2")
                    or item.select_one("h3")
                    or item.select_one("[data-testid='product-title']")
                )
                if title_node:
                    title = title_node.get_text(strip=True)
                else:
                    # Extract title from text before first R$
                    title = re.split(r"R\$", all_text)[0].strip()
                    # Clean up rating patterns
                    title = re.sub(r"\d+[.,]\d+\s*\(\d+\)", "", title).strip()

                if not title or len(title) < 5:
                    continue

                # link
                href = item.get("href", "")
                if not href:
                    link_el = item.find("a", href=True)
                    href = link_el.get("href", "") if link_el else ""

                if href and not href.startswith("http"):
                    href = f"https://www.magazineluiza.com.br{href}"

                affiliate_link = self._convert_to_affiliate_link(href)

                # prices from text
                price_matches = re.findall(r"R\$\s*([\d.,]+)", all_text)
                if not price_matches:
                    continue

                prices = []
                for pm in price_matches:
                    p = self._parse_price(f"R$ {pm}")
                    if p and p > 0:
                        prices.append(p)

                if not prices:
                    continue

                price = min(prices)  # best/lowest price
                old_price = max(prices) if len(prices) > 1 and max(prices) > price else None

                discount = 0.0
                if old_price and old_price > price:
                    discount = round((1 - price / old_price) * 100, 1)

                # discount from text (e.g. "10% OFF")
                disc_match = re.search(r"(\d+)%\s*(?:OFF|off|desc)", all_text)
                if disc_match and discount == 0:
                    discount = float(disc_match.group(1))
                    if not old_price:
                        old_price = round(price / (1 - discount / 100), 2)

                # image
                img_node = item.select_one("img")
                img_url = ""
                if img_node:
                    img_url = img_node.get("src") or img_node.get("data-src") or ""

                # installment
                installment_text = ""
                inst_match = re.search(r"(\d+x\s+de\s+R\$\s*[\d.,]+(?:\s+sem\s+juros)?)", all_text, re.IGNORECASE)
                if inst_match:
                    installment_text = inst_match.group(1)

                # pix discount
                pix_match = re.search(r"\((\d+%\s+de\s+desconto\s+no\s+pix)\)", all_text, re.IGNORECASE)
                pix_text = pix_match.group(1) if pix_match else ""

                if len(title) > 100:
                    title = title[:97] + "..."

                offers.append(MagaluOffer(
                    title=title,
                    price=price,
                    old_price=old_price,
                    discount_percent=discount,
                    image_url=img_url,
                    affiliate_link=affiliate_link,
                    category=category_label,
                    installment_text=installment_text,
                    pix_discount_text=pix_text,
                ))
            except Exception as e:
                logger.debug("[magalu] error parsing HTML card: %s", e)

        return offers

    # ── strategy 2: storefront page scraping ──────────────────────────

    async def _fetch_via_storefront_scrape(self, search_query: str, category_label: str) -> list[MagaluOffer]:
        """Scrapes the affiliate storefront page as a fallback."""
        search_slug = search_query.replace(" ", "+")
        url = f"{self.store_url}/busca/{search_slug}/"

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Cache-Control": "no-cache",
        }

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                # Check for captcha
                if "captcha" in resp.text.lower() or resp.status_code in (403, 429):
                    logger.warning("[magalu] captcha or block on storefront for '%s'", search_query)
                    return []
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.error("[magalu] storefront scrape error for '%s': %s", search_query, e)
            return []

        soup = BeautifulSoup(html, "html.parser")
        return self._parse_html_cards(soup, category_label)

    def _convert_to_affiliate_link(self, product_url: str) -> str:
        """Converts a magazineluiza.com.br URL to a magazinevoce.com.br affiliate link."""
        if not product_url:
            return product_url

        # If already an affiliate link, keep it
        if "magazinevoce.com.br" in product_url:
            return product_url

        # Convert standard magalu URL to affiliate storefront URL
        if "magazineluiza.com.br" in product_url:
            return product_url.replace(
                "www.magazineluiza.com.br",
                f"www.magazinevoce.com.br/magazine{self.storefront_slug}"
            )

        return product_url

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """Parses a brazilian price string like 'R$ 2.399,90' into float."""
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
        """Returns available category keys and their labels."""
        return {k: v["label"] for k, v in CATEGORY_MAP.items()}
