import os
import logging
from dotenv import load_dotenv
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.infrastructure.ai.openai_service import OpenAIService
from core.application.use_cases.send_daily_greeting import SendDailyGreeting

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting WhatsApp Sales Agent...")
    
    # 1. Initialize Infrastructure
    whatsapp_service = EvolutionWhatsAppService()
    
    # 2. Check Connection Status
    status = whatsapp_service.get_status()
    logger.info(f"WhatsApp Status: {status}")
    
    if not status.get("connected"):
        logger.warning("WhatsApp is NOT connected.")
        qr_code = whatsapp_service.get_qrcode()
        if qr_code:
            logger.info("QR Code generated successfully. (Base64 available)")
        else:
            logger.error("Failed to generate QR Code.")
        return

    # 3. Initialize AI Service
    try:
        ai_service = OpenAIService()
        logger.info("AI Service initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize AI Service: {e}")
        ai_service = None

    # 4. Execute Use Case (Example)
    target = os.environ.get("TEST_TARGET_JID", "status@broadcast")
    greeting_use_case = SendDailyGreeting(whatsapp_service)
    
    # Generate AI Greeting if service is available
    message = "Bom dia, pessoal! Como vocês estão?"
    if ai_service:
        ai_response = ai_service.chat("Gere uma saudação curta e amigável de bom dia para um grupo de vendas no WhatsApp.")
        if ai_response:
            message = ai_response

    logger.info(f"Attempting to send message to: {target}")
    greeting_use_case.execute(target, message=message)

if __name__ == "__main__":
    main()

