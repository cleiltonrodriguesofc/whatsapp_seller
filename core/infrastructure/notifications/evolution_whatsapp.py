import os
import httpx
import logging
import base64
import uuid
from typing import Optional

from core.application.interfaces import NotificationService

logger = logging.getLogger(__name__)


class EvolutionWhatsAppService(NotificationService):
    """
    Sends WhatsApp messages via a self-hosted Evolution API instance.
    Now optimized with asynchronous I/O using httpx.
    """

    def __init__(self, instance: Optional[str] = None, apikey: Optional[str] = None):
        self.base_url = os.environ.get("EVOLUTION_API_URL", "http://evolution-api:8080")
        self.api_key = apikey or os.environ.get("EVOLUTION_API_KEY", "changeme")
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
            # Use unified send_status for reliability
            return await self.send_status(content=media, type="image", caption=caption)
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
                        res = await client.post(url, data=payload, files=files, headers=headers)
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
        caption: str = "",
    ) -> bool:
        """
        Sends a status update (text or image).
        """
        url = f"{self.base_url}/message/sendStatus/{self.instance}"
        is_url = content.startswith("http")

        # Format content for status images if it's base64/local
        final_content = content
        if type == "image" and not is_url and not content.startswith("data:"):
            final_content = f"data:image/jpeg;base64,{content}"

        payload = {
            "type": type,
            "content": final_content,
            "allContacts": True if not jid_list else False,
        }

        if type == "image":
            payload["caption"] = caption

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
                    logger.error(
                        "Evolution API Status Error (%s): %s | Payload: %s",
                        response.status_code,
                        response.text,
                        payload,
                    )
                response.raise_for_status()
                logger.info(
                    "WhatsApp Status update sent successfully to %s", "all contacts" if not jid_list else jid_list
                )
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
                if not isinstance(data, dict):
                    return {"status": "error", "connected": False, "error": "Invalid response type"}

                # Robustly get state
                instance_data = data.get("instance")
                if isinstance(instance_data, dict):
                    state = instance_data.get("state", "unknown")
                elif isinstance(instance_data, str):
                    state = instance_data
                else:
                    state = data.get("state", "unknown")  # Fallback for different API versions

                return {"status": state, "connected": state in ["open", "CONNECTED"]}
        except Exception as exc:
            logger.error("Failed to get WhatsApp status: %s", exc)
            return {"status": "error", "connected": False}

    async def create_instance(self, name: str, display_name: str = None) -> Optional[dict]:
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
        if display_name:
            # Evolution v2 / Baileys expects an array [Browser, Device, Version] to show a custom name
            payload["browser"] = [display_name, "Chrome", "1.0"]
            payload["clientName"] = display_name
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                if response.status_code >= 400:
                    logger.error("Evolution Create Instance Error (%s): %s", response.status_code, response.text)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    return data
                return {"success": True, "message": str(data)}  # Wrap if it's a string
        except Exception as exc:
            logger.error("Failed to create WhatsApp instance %s: %s", name, exc)
            return None

    async def _ensure_instance_exists(self, display_name: str = None) -> bool:
        logger.info(f"Ensuring instance {self.instance} exists...")
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance,
            "token": self.api_key,  # Use api_key as token
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        if display_name:
            # Evolution v2 / Baileys expects an array [Browser, Device, Version] to show a custom name
            payload["browser"] = [display_name, "Chrome", "1.0"]
            payload["clientName"] = display_name
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                if response.status_code in [201, 200]:
                    logger.info("Instance %s created/ensured.", self.instance)
                    return True
                elif response.status_code == 403:
                    logger.info("Instance %s already exists.", self.instance)
                    return True
                logger.warning("Unexpected status during instance ensure: %s - %s", response.status_code, response.text)
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
                if isinstance(data, dict):
                    return data.get("base64", "") or data.get("code", "")
                elif isinstance(data, str):
                    return data  # If API returns string directly
                return ""
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp QR Code: %s", exc)
            return ""

    async def set_presence(self, phone: str, presence: str = "composing", delay: int = 1200) -> bool:
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

    async def delete_instance(self) -> bool:
        url = f"{self.base_url}/instance/delete/{self.instance}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=self._headers())
                if response.status_code >= 400:
                    logger.error("Evolution Delete Instance Error (%s): %s", response.status_code, response.text)
                return response.status_code in [200, 201]
        except Exception as exc:
            logger.error("Failed to delete WhatsApp instance: %s", exc)
            return False

    async def logout_instance(self) -> bool:
        url = f"{self.base_url}/instance/logout/{self.instance}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=self._headers())
                if response.status_code >= 400:
                    logger.error("Evolution Logout Error (%s): %s", response.status_code, response.text)
                return response.status_code in [200, 201]
        except Exception as exc:
            logger.error("Failed to logout WhatsApp instance: %s", exc)
            return False

    async def send_group_closing_announcement(
        self, group_jid: str, message: str, winners: list, admin_name: str
    ) -> bool:
        return await self.send_text(group_jid, message)

    async def send_payment_reminder(self, number: str, product_name: str, message: str, affiliate_link: str) -> bool:
        return await self.send_text(number, message)

    async def send_prize_notification(self, number: str, product_name: str, message: str, affiliate_link: str) -> bool:
        return await self.send_text(number, message)
