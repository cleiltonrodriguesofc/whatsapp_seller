"""
promotional card image generator for magalu affiliate offers.
generates a visually appealing card matching the official magazine voce design
using html/css rendered via playwright for pixel-perfect results.
"""

import asyncio
import base64
import logging
import httpx

logger = logging.getLogger(__name__)

_browser_semaphore = None

def _get_semaphore():
    global _browser_semaphore
    if _browser_semaphore is None:
        _browser_semaphore = asyncio.Semaphore(1)
    return _browser_semaphore

async def _download_image_b64(url: str) -> str:
    """downloads an image and returns it as a base64 data URI."""
    if not url:
        return ""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            })
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "image/jpeg")
                b64 = base64.b64encode(resp.content).decode("utf-8")
                return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning("[promo-card] failed to download image: %s", e)
    return ""

async def generate_promo_card(
    title: str,
    price: float,
    old_price: float | None,
    discount_percent: float,
    image_url: str,
    storefront_name: str = "cleiltontec",
    store_type: str = "magalu",
    theme_color: str = "#0088ff",
    tagline: str = "tem na minha loja",
    installment_text: str = "",
    pix_discount_text: str = "",
    owner_avatar_b64: str = "",
) -> bytes:
    """generates a high-quality promotional card matching the magalu influencer style."""
    
    # download product image
    b64_image = await _download_image_b64(image_url)
    img_src = b64_image if b64_image else image_url
    img_tag = f'<img src="{img_src}" class="product-image">' if img_src else ""

    # format prices
    old_str = ""
    if old_price and old_price > price:
        old_str = f"R$ {old_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    price_str = f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    installment_str = installment_text if installment_text else ""

    # build avatar html from db-stored base64 or fallback to emoji
    avatar_html = "👨🏽‍🦱"
    if owner_avatar_b64:
        img_src = owner_avatar_b64 if owner_avatar_b64.startswith("data:image") else f"data:image/jpeg;base64,{owner_avatar_b64}"
        avatar_html = f'<img src="{img_src}" style="width: 100%; height: 100%; object-fit: cover; object-position: center 15%;">'

    text_color = "white"
    if store_type == "mercadolivre":
        theme_color = "#FFE600"
        text_color = "#2D3277"

    logo_html = ""
    if store_type == "magalu":
        logo_html = """
                <div class="magalu-logo">
                    <svg width="80" height="80" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M50 0L63 37L100 50L63 63L50 100L37 63L0 50L37 37L50 0Z" fill="#FF0055"/>
                        <path d="M50 15L59.5 40.5L85 50L59.5 59.5L50 85L40.5 59.5L15 50L40.5 40.5L50 15Z" fill="#0066FF"/>
                        <path d="M50 25L57 43L75 50L57 57L50 75L43 57L25 50L43 43L50 25Z" fill="#FFEA00"/>
                        <path d="M42 50L48 56L62 42" stroke="white" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <div class="text">influenciador<br>magalu</div>
                </div>
        """
    elif store_type == "mercadolivre":
        try:
            import os
            logo_path = os.path.join(os.path.dirname(__file__), "assets", "ml_logo.png")
            with open(logo_path, "rb") as f:
                ml_logo_b64 = base64.b64encode(f.read()).decode("utf-8")
            logo_html = f"""
                <div class="magalu-logo">
                    <img src="data:image/png;base64,{ml_logo_b64}" width="100" height="100" style="border-radius: 12px; margin-right: 15px;">
                    <div class="text" style="color: #2D3277; font-size: 38px; line-height: 1;">mercado<br>livre</div>
                </div>
            """
        except Exception as e:
            logger.warning("Failed to load ml_logo.png: %s", e)
            logo_html = """
                <div class="magalu-logo">
                    <svg width="80" height="80" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="50" cy="50" r="50" fill="#2D3277"/>
                        <path d="M25 50 L45 50 L65 30 M45 50 L60 65 L80 45" stroke="#FFE600" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                    </svg>
                    <div class="text" style="color: #2D3277;">mercado<br>livre</div>
                </div>
        """
    else:
        logo_html = f"""
                <div class="magalu-logo">
                    <div class="text" style="font-size: 50px; color: {text_color};">{store_type}</div>
                </div>
        """

    # format tagline dynamically: bold the first word, remove spaces from the rest
    if tagline == "tem na minha loja":
        formatted_tagline = "<span>tem</span>naminhaloja"
    else:
        parts = tagline.split(" ", 1)
        if len(parts) > 1:
            formatted_tagline = f"<span>{parts[0]}</span>{parts[1].replace(' ', '')}"
        else:
            formatted_tagline = tagline

    # HTML Template perfectly matching the reference design
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0; padding: 0;
                width: 1080px; height: 1920px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: {theme_color};
                display: flex; flex-direction: column; align-items: center;
                overflow: hidden;
                position: relative;
            }}
            
            /* Gradient Overlays */
            .bg-gradient-1 {{
                position: absolute; top: -10%; left: -10%;
                width: 70%; height: 50%;
                background: radial-gradient(circle, rgba(0, 200, 255, 0.6) 0%, transparent 70%);
                z-index: 0;
            }}
            .bg-gradient-2 {{
                position: absolute; bottom: -20%; right: -20%;
                width: 80%; height: 80%;
                background: radial-gradient(circle, rgba(0, 50, 255, 0.4) 0%, transparent 70%);
                z-index: 0;
            }}
            
            /* Rainbow Side Bar */
            .side-bar {{
                position: absolute; left: 0; top: 0; bottom: 0; width: 30px;
                background: { "linear-gradient(to bottom, #ffea00 0%, #ff0055 33%, #0066ff 66%, #00cc00 100%)" if store_type == "magalu" else ("rgba(45, 50, 119, 1)" if store_type == "mercadolivre" else "rgba(255,255,255,0.3)") };
                z-index: 2;
            }}

            .content {{
                position: relative; z-index: 1;
                width: 100%; height: 100%;
                display: flex; flex-direction: column; align-items: center;
                padding: 90px 70px 80px 70px;
            }}

            /* HEADER */
            .header {{
                display: flex; flex-direction: column; align-items: center;
                margin-bottom: 55px; width: 100%;
            }}
            .magalu-logo {{
                display: flex; align-items: center; gap: 20px; margin-bottom: 25px;
            }}
            .magalu-logo .text {{
                color: {text_color}; font-size: 38px; font-weight: 800; line-height: 1.1;
                text-transform: lowercase;
            }}

            .user-info {{
                display: flex; align-items: center; gap: 25px; margin-bottom: 0px;
            }}
            .user-avatar {{
                width: 120px; height: 120px; border-radius: 35px;
                background: #f0c080; border: 4px solid {text_color};
                display: flex; align-items: center; justify-content: center;
                font-size: 70px; overflow: hidden;
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            }}
            .user-name {{
                color: {text_color}; font-size: 65px; font-weight: 800;
                text-shadow: {"none" if store_type == "mercadolivre" else "0 4px 10px rgba(0,0,0,0.1)"};
            }}

            .tagline {{
                color: {text_color}; font-size: 100px; font-weight: 900;
                letter-spacing: -3px; text-shadow: {"none" if store_type == "mercadolivre" else "0 8px 20px rgba(0,0,0,0.15)"};
                margin-top: -5px;
            }}
            .tagline span {{ font-weight: 700; }}

            /* PRODUCT CARD */
            .card {{
                background: white;
                border-radius: 50px;
                width: 100%;
                padding: 60px 60px;
                box-shadow: 0 30px 60px rgba(0,0,0,0.25);
                display: flex; flex-direction: column;
            }}
            .product-image-container {{
                width: 100%; height: 580px;
                display: flex; align-items: center; justify-content: center;
                margin-bottom: 25px;
            }}
            .product-image {{
                width: 100%; height: 100%; object-fit: contain;
                transform: scale(1.05);
            }}

            .product-title {{
                color: #000; font-size: 42px; font-weight: 800; line-height: 1.35;
                margin-bottom: 30px;
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}

            .price-section {{
                display: flex; flex-direction: column; gap: 12px;
            }}
            .old-price {{
                color: #a0a0a0; font-size: 30px; text-decoration: line-through; font-weight: 700;
                min-height: 36px;
            }}
            .installments {{
                color: #444; font-size: 32px; font-weight: 800;
                min-height: 38px;
            }}
            .current-price-row {{
                display: flex; align-items: center; gap: 20px; margin-top: 15px;
            }}
            .ou-text {{ color: #555; font-size: 32px; font-weight: 700; }}
            .price-box {{
                background: {"#2D3277" if store_type == "mercadolivre" else theme_color}; color: {"#FFE600" if store_type == "mercadolivre" else "white"};
                padding: 15px 30px; border-radius: 16px;
                font-size: 65px; font-weight: 900;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }}
            .no-pix {{ color: #555; font-size: 32px; font-weight: 700; }}

            .discount-text {{
                color: #00b853; font-size: 30px; font-weight: 800; margin-top: 15px;
                min-height: 36px;
            }}

            /* BOTTOM CTA */
            .cta-section {{
                margin-top: auto; width: 100%;
                display: flex; align-items: center; justify-content: space-between;
                padding: 0 10px;
            }}
            .cta-text {{
                color: {text_color}; font-size: 65px; font-weight: 800; line-height: 1.1;
                text-shadow: {"none" if store_type == "mercadolivre" else "0 4px 10px rgba(0,0,0,0.1)"};
            }}
            .cta-text span {{
                text-decoration: underline; text-decoration-thickness: 6px; text-underline-offset: 8px;
            }}
            .cta-arrows {{
                color: {"rgba(45, 50, 119, 0.7)" if store_type == "mercadolivre" else "rgba(255,255,255,0.7)"}; font-size: 80px; font-weight: 900; letter-spacing: -6px;
                margin-top: 10px;
            }}
            .cta-button {{
                width: 380px; height: 110px;
                background: white; border-radius: 60px;
                box-shadow: 0 15px 30px rgba(0,0,0,0.2);
            }}
        </style>
    </head>
    <body>
        <div class="side-bar"></div>
        <div class="bg-gradient-1"></div>
        <div class="bg-gradient-2"></div>
        
        <div class="content">
            <!-- HEADER -->
            <div class="header">
                {logo_html}
                
                <div class="user-info">
                    <div class="user-avatar">{avatar_html}</div>
                    <div class="user-name">{storefront_name.capitalize()}</div>
                </div>
                
                <div class="tagline">{formatted_tagline}</div>
            </div>

            <!-- CARD -->
            <div class="card">
                <div class="product-image-container">
                    {img_tag}
                </div>
                
                <div class="product-title">{title}</div>
                
                <div class="price-section">
                    <div class="old-price">{old_str}</div>
                    <div class="installments">{installment_str}</div>
                    
                    <div class="current-price-row">
                        <div class="ou-text">ou</div>
                        <div class="price-box">{price_str}</div>
                        <div class="no-pix">no PIX</div>
                    </div>
                    
                    <div class="discount-text">{f"({pix_discount_text})" if pix_discount_text else (f"({discount_percent:.0f}% de desconto no PIX)" if discount_percent > 0 else "")}</div>
                </div>
            </div>

            <!-- CTA -->
            <div class="cta-section">
                <div class="cta-text">
                    Clique<br><span>e confira</span>
                </div>
                <div class="cta-arrows">&gt;&gt;&gt;</div>
                <div class="cta-button"></div>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        def _render_sync(html):
            from playwright.sync_api import sync_playwright
            import gc
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                page = browser.new_page(
                    viewport={'width': 1080, 'height': 1920},
                    device_scale_factor=1
                )
                # Use domcontentloaded instead of load to avoid blocking
                # on external resources (Google Fonts) in restricted environments.
                page.set_content(html, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
                screenshot = page.screenshot(type="png")
                browser.close()
            gc.collect()
            return screenshot

        sem = _get_semaphore()
        async with sem:
            screenshot = await asyncio.to_thread(_render_sync, html_content)
            
        if not screenshot:
            logger.error("[promo-card] playwright returned empty screenshot")
            return b""
        logger.info("[promo-card] card generated successfully (%d bytes)", len(screenshot))
        return screenshot
    except Exception as e:
        logger.error("[promo-card] playwright generation failed: %s", e, exc_info=True)
        return b""
