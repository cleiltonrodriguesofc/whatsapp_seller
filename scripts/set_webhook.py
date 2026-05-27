import asyncio, os
from dotenv import load_dotenv; load_dotenv()
import httpx
from core.infrastructure.database.session import SessionLocal
from core.infrastructure.database.models import InstanceModel

db = SessionLocal()
inst = db.query(InstanceModel).filter(InstanceModel.user_id == 1).first()
base = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")

webhook_url = "https://whatsellerpro.onrender.com/webhook/evolution"
print(f"Setting webhook to: {webhook_url}")

async def set_webhook():
    headers = {"apikey": inst.apikey, "Content-Type": "application/json"}
    payload = {
        "webhook": {
            "enabled": True,
            "url": webhook_url,
            "byEvents": False,
            "base64": False,
            "events": [
                "CONNECTION_UPDATE",
                "MESSAGES_UPSERT",
                "CONTACTS_UPSERT",
            ],
        }
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{base}/webhook/set/{inst.name}", json=payload, headers=headers)
        print(f"status: {r.status_code}")
        print(f"response: {r.text[:500]}")

asyncio.run(set_webhook())
db.close()
