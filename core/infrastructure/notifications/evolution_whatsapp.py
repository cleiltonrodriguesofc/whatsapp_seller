import os
import httpx
import logging
import asyncio
import base64
from typing import Optional

from core.application.interfaces import NotificationService

logger = logging.getLogger(__name__)


class EvolutionWhatsAppService(NotificationService):
    """
    Sends WhatsApp messages via a self-hosted Evolution API instance.
    Now optimized with asynchronous I/O using httpx.
    """

    def __init__(self, instance: Optional[str] = None):
        self.base_url = os.environ.get("EVOLUTION_API_URL", "http://evolution-api:8080")
        self.api_key = os.environ.get("EVOLUTION_API_KEY", "changeme")
        self.instance = instance or os.environ.get("EVOLUTION_INSTANCE", "grupo_1000")
        self.timeout = httpx.Timeout(300.0, connect=30.0)

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

    async def send_image(self, phone: str, media: str, caption: str = "") -> bool:
        """
        Sends an image with an optional caption using multipart/form-data for reliability.
        """
        # We'll convert base64 back to binary if it's not a URL
        is_url = media.startswith("http")

        if phone == "status@broadcast":
            url = f"{self.base_url}/message/sendStatus/{self.instance}"
            payload = {
                "type": "image",
                "content": media if is_url else f"data:image/jpeg;base64,{media}",
                "caption": caption,
                "allContacts": True,
                "mimetype": "image/jpeg",
            }
            # For Status, Evolution API v2 often only supports JSON with URL/Base64
            # We'll try JSON first for Status.
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(url, json=payload, headers=self._headers())
                    if res.status_code >= 400:
                        logger.error("Status Error: %s", res.text)
                    res.raise_for_status()
                    return True
            except Exception as e:
                logger.error("sendStatus failed: %s", e)
                return False
        else:
            # For direct messages, we use sendMedia with multipart if possible
            url = f"{self.base_url}/message/sendMedia/{self.instance}"

            if is_url:
                payload = {
                    "number": self._clean_phone(phone),
                    "mediatype": "image",
                    "media": media,
                    "caption": caption,
                }
                headers = self._headers()
                files = None
            else:
                # Convert base64 to bytes
                image_bytes = base64.b64decode(media.split(",")[-1])
                files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
                payload = {
                    "number": self._clean_phone(phone),
                    "mediatype": "image",
                    "caption": caption,
                }
                headers = {"apikey": self.api_key}  # httpx handles boundary

            # Base headers
            headers = {"apikey": self.api_key}

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if files:
                        # For multipart, do NOT set Content-Type, httpx will do it
                        res = await client.post(
                            url, data=payload, files=files, headers=headers
                        )
                    else:
                        # For JSON, set it
                        headers["Content-Type"] = "application/json"
                        res = await client.post(url, json=payload, headers=headers)

                    if res.status_code >= 400:
                        logger.error("Media Error (%s): %s", res.status_code, res.text)
                    res.raise_for_status()
                    return True
            except Exception as e:
                logger.error("sendMedia failed: %r", e)
                return False

    async def send_status(
        self,
        content: str,
        type: str = "text",
        jid_list: list = None,
        backgroundColor: str = "#128C7E",
        font: int = 1,
    ) -> bool:
        """
        Sends a status update (text or image).
        """
        url = f"{self.base_url}/message/sendStatus/{self.instance}"
        payload = {
            "type": type,
            "content": content,
            "allContacts": True if not jid_list else False,
        }

        if type == "text":
            payload["backgroundColor"] = backgroundColor
            payload["font"] = font
        else:
            # For images
            payload["mimetype"] = "image/jpeg"
            payload["fileName"] = "status.jpg"

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

    async def create_instance(self, name: str) -> Optional[dict]:
        """
        Creates a new WhatsApp instance.
        """
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": name,
            "token": str(uuid.uuid4()),  # Unique token for the instance
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.error("Failed to create WhatsApp instance %s: %s", name, exc)
            return None

    async def _ensure_instance_exists(self) -> bool:
        logger.info(f"Ensuring instance {self.instance} exists...")
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
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

    async def set_presence(
        self, phone: str, presence: str = "composing", delay: int = 1200
    ) -> bool:
        """
        Simulates "Typing..." or "Recording..." presence.
        presences: 'composing', 'recording', 'paused'
        """
        # Based on Evolution API v2.2.x observed diagnostic results
        url = f"{self.base_url}/chat/sendPresence/{self.instance}"
        payload = {
            "number": self._clean_phone(phone) if "@" not in phone else phone,
            "presence": presence,
            "delay": delay,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                if response.status_code >= 400:
                    logger.error("Evolution API Presence Error: %s", response.text)
                response.raise_for_status()
                return True
        except Exception as exc:
            logger.error("Failed to set presence: %s", exc)
            return False

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

    async def send_group_closing_announcement(
        self, group_jid: str, message: str, winners: list, admin_name: str
    ) -> bool:
        return await self.send_text(group_jid, message)

    async def send_payment_reminder(
        self, number: str, product_name: str, message: str, affiliate_link: str
    ) -> bool:
        return await self.send_text(number, message)

    async def send_prize_notification(
        self, number: str, product_name: str, message: str, affiliate_link: str
    ) -> bool:
        return await self.send_text(number, message)
