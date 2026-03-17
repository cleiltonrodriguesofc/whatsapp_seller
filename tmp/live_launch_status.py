import asyncio
import os
import logging
from dotenv import load_dotenv
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.application.services.humanized_sender import HumanizedSender

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

load_dotenv()


async def launch_status_sequence():
    service = EvolutionWhatsAppService()
    sender = HumanizedSender(service)

    # Sequence of slides (Image Path, Caption)
    slides = [
        (
            r"C:\Users\cleil\.gemini\antigravity\brain\f06bbb14-522c-45aa-ad7b-d2e8011ff516\whatsapp_sales_hero_premium_1773691725200.png",
            "O dia em que parei de 'trabalhar' no WhatsApp e comecei a gerenciar ativos. 💎",
        ),
        (
            r"C:\Users\cleil\.gemini\antigravity\brain\f06bbb14-522c-45aa-ad7b-d2e8011ff516\whatsapp_sales_pain_points_1_1773690272825.png",
            "A verdade? Eu cansei. Cansei de ver vendas sendo perdidas porque levei 10 minutos para responder. Vender pelo WhatsApp é uma arte, mas o gerenciamento manual é um buraco negro de tempo.",
        ),
        (
            r"C:\Users\cleil\.gemini\antigravity\brain\f06bbb14-522c-45aa-ad7b-d2e8011ff516\whatsapp_ai_order_processing_2_1773690288662.png",
            "Por isso, construí o WhatsApp Sales Agent. 🤖🚀\n\nNão é um 'bot' burro. É uma IA que lê a conversa, separa o pedido e confere o estoque automaticamente. É o fim da digitação infinita.",
        ),
        (
            r"C:\Users\cleil\.gemini\antigravity\brain\f06bbb14-522c-45aa-ad7b-d2e8011ff516\whatsapp_sales_success_3_1773690304518.png",
            "Toda essa sequência foi agendada por essa tecnologia. Ela trabalha enquanto eu tomo café. ☕🔥\n\nResponda 'VOU TESTAR' aqui no privado se você quer ser um dos primeiros a ver essa mágica funcionando. 👇📈",
        ),
    ]

    logger.info("Starting Resilient Status Launch Sequence...")
    target = "status@broadcast"

    for i, (img_path, caption) in enumerate(slides):
        logger.info(f"--- Processing Slide {i} ---")

        # Try sending with image
        success = await sender.send_campaign_humanized(
            targets=[target], content=caption, media_url=img_path
        )

        if not success:
            logger.warning(
                f"Slide {i} image failed. Retrying with TEXT-ONLY fallback..."
            )
            # Fallback to text-only status
            success = await sender.send_campaign_humanized(
                targets=[target], content=caption, media_url=None
            )

        if success:
            logger.info(
                f"Slide {i} delivered successfully (Status: {'Media' if img_path else 'Text'})."
            )
        else:
            logger.error(f"Slide {i} COMPLETELY FAILED.")

        if i < len(slides) - 1:
            delay = 45  # 45s between slides for visibility
            logger.info(f"Waiting {delay}s for sequence visibility...")
            await asyncio.sleep(delay)

    logger.info("Resilient Status Sequence Completed!")


if __name__ == "__main__":
    asyncio.run(launch_status_sequence())
