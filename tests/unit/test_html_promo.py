import asyncio
from playwright.async_api import async_playwright
import os

import asyncio
import time
from core.infrastructure.gateways.magalu_gateway import MagaluGateway
from core.infrastructure.image.promo_card_generator import generate_promo_card
from core.infrastructure.ai.openai_service import OpenAIService
from core.infrastructure.database.session import SessionLocal
from core.infrastructure.utils.shortener import get_or_create_shortlink
from core.infrastructure.database.models import Base
from core.infrastructure.database.session import engine

Base.metadata.create_all(bind=engine)

async def test_iphone_promo():
    print("Buscando iPhone no Magalu (scraper real)...")
    gateway = MagaluGateway(storefront_slug="cleiltontec")
    
    # Busca asus i5
    offers = await gateway.get_offers(
        categories=["notebook"],
        min_discount_percent=0.0,
        max_offers=30
    )
    
    target_offer = None
    for offer in offers:
        if "asus" in offer.title.lower() and "i5" in offer.title.lower():
            target_offer = offer
            break
            
    if not target_offer:
        print("Nenhum Asus i5 encontrado. Pegando o primeiro notebook...")
        if offers:
            target_offer = offers[0]
        else:
            print("Nenhuma oferta de notebook encontrada.")
            return

    print(f"Gerando arte para: {target_offer.title}")
    
    # Generate the image
    card_bytes = await generate_promo_card(
        title=target_offer.title,
        price=target_offer.price,
        old_price=target_offer.old_price,
        discount_percent=target_offer.discount_percent,
        image_url=target_offer.image_url,
        storefront_name="cleiltontec",
        store_type="magalu",
        theme_color="#0088ff",
        tagline="tem na minha loja",
        installment_text=target_offer.installment_text,
        pix_discount_text=target_offer.pix_discount_text,
    )
    
    
    print("\n--- GERANDO COPY COM IA ---")
    db = SessionLocal()
    try:
        short_link = get_or_create_shortlink(db, target_offer.affiliate_link, "cleiltontec")
    finally:
        db.close()
        
    ai_service = OpenAIService()
    copy = await ai_service.generate_affiliate_copy(
        title=target_offer.title,
        price=target_offer.price,
        old_price=target_offer.old_price,
        discount=target_offer.discount_percent,
        link=short_link
    )
    print(copy)
    print("---------------------------\n")

    if card_bytes:
        timestamp = int(time.time())
        filename = f"test_asus_{timestamp}.png"
        with open(filename, "wb") as f:
            f.write(card_bytes)
        print(f"Salvo em {filename} com sucesso!")
        
        print(f"Link de Afiliado: {target_offer.affiliate_link}")
    else:
        print("Erro ao gerar a imagem.")

if __name__ == "__main__":
    asyncio.run(test_iphone_promo())
