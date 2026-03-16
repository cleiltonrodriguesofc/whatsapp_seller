import os
import httpx
import logging
import asyncio

from core.application.interfaces import NotificationService

logger = logging.getLogger(__name__)


class EvolutionWhatsAppService(NotificationService):
    """
    Sends WhatsApp messages via a self-hosted Evolution API instance.
    Now optimized with asynchronous I/O using httpx.
    """

    def __init__(self):
        self.base_url = os.environ.get("EVOLUTION_API_URL", "http://evolution-api:8080")
        self.api_key = os.environ.get("EVOLUTION_API_KEY", "changeme")
        self.instance = os.environ.get("EVOLUTION_INSTANCE", "grupo_1000")
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    def _headers(self) -> dict:
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    def _clean_phone(self, phone: str) -> str:
        digits = "".join(filter(str.isdigit, phone))
        if not digits.startswith("55") and len(digits) <= 11:
            digits = "55" + digits
        return digits

    async def send_text(self, phone: str, message: str) -> bool:
        """
        Sends a text message asynchronously. Detects if it's a Status update.
        """
        if phone == "status@broadcast":
            return await self.send_status(message)

        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {
            "number": self._clean_phone(phone) if "@" not in phone else phone,
            "text": message,
            "linkPreview": False,
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                if response.status_code >= 400:
                    logger.error("Evolution API Error Response: %s", response.text)
                response.raise_for_status()
                return True
        except Exception as exc:
            logger.error("evolution-api send failed: %s", exc)
            return False

    async def send_status(self, message: str, jid_list: list = None) -> bool:
        """
        Sends a text status update to WhatsApp Status.
        """
        url = f"{self.base_url}/message/sendStatus/{self.instance}"
        payload = {
            "type": "text",
            "content": message,
            "backgroundColor": "#128C7E", # WhatsApp Green
            "font": 1,
            "allContacts": True if not jid_list else False
        }
        if jid_list:
            payload["statusJidList"] = jid_list

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                if response.status_code >= 400:
                    logger.error("Evolution API Status Error: %s", response.text)
                response.raise_for_status()
                return True
        except Exception as exc:
            logger.error("evolution-api sendStatus failed: %s", exc)
            return False

    async def send_group_text(self, group_jid: str, message: str) -> bool:
        return await self.send_text(group_jid, message)

    async def get_contacts(self) -> list:
        url = f"{self.base_url}/chat/fetchAllChats/{self.instance}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._headers())
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp contacts: %s", exc)
            return []

    async def get_groups(self) -> list:
        url = f"{self.base_url}/group/fetchAllGroups/{self.instance}?getParticipants=false"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._headers())
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp groups: %s", exc)
            return []

    async def get_status(self) -> dict:
        url = f"{self.base_url}/instance/connectionState/{self.instance}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self._headers())
                if response.status_code == 404:
                    return {"status": "not_found", "connected": False}
                response.raise_for_status()
                data = response.json()
                state = data.get("instance", {}).get("state", "unknown")
                return {"status": state, "connected": state == "open"}
        except Exception as exc:
            logger.error("Failed to get WhatsApp status: %s", exc)
            return {"status": "error", "connected": False}

    async def _ensure_instance_exists(self) -> bool:
        logger.info(f"Ensuring instance {self.instance} exists...")
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                if response.status_code in [201, 200, 403]:
                    return True
                return False
        except Exception as exc:
            logger.error("Failed to ensure WhatsApp instance exists: %s", exc)
            return False

    async def get_qrcode(self) -> str:
        url = f"{self.base_url}/instance/connect/{self.instance}?base64=true"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=self._headers())
                if response.status_code == 404:
                    if await self._ensure_instance_exists():
                        response = await client.get(url, headers=self._headers())
                    else:
                        return ""
                
                response.raise_for_status()
                data = response.json()
                return data.get("base64", "")
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp QR Code: %s", exc)
            return ""

    async def disconnect_instance(self) -> bool:
        url = f"{self.base_url}/instance/logout/{self.instance}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(url, headers=self._headers())
                response.raise_for_status()
                return True
        except Exception as exc:
            logger.error("Failed to disconnect WhatsApp: %s", exc)
            return False
