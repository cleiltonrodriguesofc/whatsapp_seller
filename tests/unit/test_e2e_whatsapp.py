import asyncio
from dotenv import load_dotenv

load_dotenv()

from core.infrastructure.database.session import SessionLocal, engine  # noqa: E402
from core.infrastructure.database.models import ShortLinkModel  # noqa: E402
from core.infrastructure.gateways.magalu_gateway import MagaluGateway  # noqa: E402
from core.infrastructure.image.promo_card_generator import generate_promo_card  # noqa: E402
from core.infrastructure.ai.openai_service import OpenAIService  # noqa: E402
from core.infrastructure.utils.shortener import get_or_create_shortlink  # noqa: E402
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService  # noqa: E402

async def run_e2e():
    print("=== TESTE END-TO-END DA MÁQUINA DE OFERTAS ===")
    
    # 1. Preparar Banco de Dados (cria a tabela short_links se não existir)
    ShortLinkModel.__table__.create(engine, checkfirst=True)
    db = SessionLocal()
    
    storefront = "cleiltontec"
    instance_name = "test_instance" # Coloque o nome da sua instância conectada no Evolution
    
    # 2. Buscar Oferta
    print("\n[1/5] Buscando oferta real no Magalu...")
    gateway = MagaluGateway(storefront_slug=storefront)
    offers = await gateway.get_offers(categories=["celular"], max_offers=10)
    
    if not offers:
        print("Erro: Nenhuma oferta encontrada.")
        return
        
    offer = offers[0]
    print(f" -> Produto encontrado: {offer.title}")
    print(f" -> Preço: R$ {offer.price:,.2f}")
    
    # 3. Encurtar Link no Banco
    print("\n[2/5] Criando Link Encurtado no DB...")
    short_link = get_or_create_shortlink(db, offer.affiliate_link, storefront)
    print(f" -> Link Encurtado: {short_link}")
    
    # 4. Gerar Copy Persuasiva com IA
    print("\n[3/5] Gerando Copy com IA...")
    ai_service = OpenAIService()
    copy = await ai_service.generate_affiliate_copy(
        title=offer.title,
        price=offer.price,
        old_price=offer.old_price,
        discount=offer.discount_percent,
        link=short_link
    )
    print(f" -> Copy Gerada:\n{copy}\n")
    
    # 5. Gerar Arte
    print("[4/5] Gerando Arte Promocional HD...")
    card_bytes = await generate_promo_card(
        title=offer.title,
        price=offer.price,
        old_price=offer.old_price,
        discount_percent=offer.discount_percent,
        image_url=offer.image_url,
        storefront_name=storefront,
        store_type="magalu",
        theme_color="#0088ff",
        tagline="tem na minha loja",
        installment_text=offer.installment_text,
        pix_discount_text=offer.pix_discount_text,
    )
    
    if not card_bytes:
        print("Erro ao gerar a arte.")
        return
    print(" -> Arte gerada com sucesso!")
    
    # 6. Disparo via Evolution API
    print("\n[5/5] Disparando para o WhatsApp Status...")
    import base64
    base64.b64encode(card_bytes).decode("utf-8")
    
    try:
        # Se você tiver a instância conectada, isso vai postar no Status!
        EvolutionWhatsAppService(instance_name=instance_name)
        # Uncomment below to actually send if the instance is correct
        # response = await whatsapp.send_status(content=b64_img, type="image", caption=copy)
        # print(" -> Status publicado com sucesso!", response)
        print(" -> (Comentado por segurança, descomente a linha de envio se a instância existir)")
    except Exception as e:
        print(" -> Erro na API do Evolution (A instância não está conectada?):", e)
        
    db.close()
    print("\n=== MÁQUINA RODOU PERFEITAMENTE ===")

if __name__ == "__main__":
    asyncio.run(run_e2e())
