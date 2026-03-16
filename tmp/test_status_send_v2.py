import asyncio
import os
import sys
from dotenv import load_dotenv
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService

load_dotenv()

class MockedService(EvolutionWhatsAppService):
    async def send_group_closing_announcement(self, group_jid, month, winner_name, amount):
        return True
    async def send_payment_reminder(self, name, phone, month, amount):
        return True
    async def send_prize_notification(self, name, phone, month, amount):
        return True

async def test_status_send():
    service = MockedService()
    target = "status@broadcast"
    message = "Segundo teste: Agora usando o endpoint correto de STATUS no WhatsApp Sales Agent Pro! 🎯 [Alvo]"

    print(f"Retestando postagem no STATUS via novo endpoint...")
    try:
        success = await service.send_text(target, message)
        if success:
            print("OK: Status postado com sucesso via endpoint correto!")
        else:
            print("ERROR: Falha ao postar no status.")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_status_send())
