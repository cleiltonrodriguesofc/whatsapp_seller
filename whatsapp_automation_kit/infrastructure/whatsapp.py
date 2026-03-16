import os
import requests
import logging

logger = logging.getLogger(__name__)

class EvolutionWhatsAppService:
    """
    Sends WhatsApp messages via a self-hosted Evolution API instance.
    Docs: https://doc.evolution-api.com
    """

    def __init__(self):
        self.base_url = os.environ.get("EVOLUTION_API_URL")
        self.api_key = os.environ.get("EVOLUTION_API_KEY")
        self.instance = os.environ.get("EVOLUTION_INSTANCE")

    def _headers(self) -> dict:
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    def _clean_phone(self, phone: str) -> str:
        """Strips formatting characters from phone numbers."""
        digits = "".join(filter(str.isdigit, phone))
        if not digits.startswith("55"):
            digits = "55" + digits
        return digits

    def send_text(self, phone: str, message: str) -> bool:
        """Sends a text message to a phone number or Group JID."""
        if not self.base_url or not self.api_key or not self.instance:
            logger.error("WhatsApp credentials not set in environment")
            return False

        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {
            "number": self._clean_phone(phone) if "@" not in phone else phone,
            "text": message,
            "linkPreview": False,
        }
        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=10)
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.error("WhatsApp send failed: %s", exc)
            return False

    def send_group_text(self, group_jid: str, message: str) -> bool:
        return self.send_text(group_jid, message)

    def get_groups(self) -> list:
        """Fetches the list of groups the instance is part of."""
        url = f"{self.base_url}/group/fetchAllGroups/{self.instance}?getParticipants=false"
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp groups: %s", exc)
            return []

    def get_status(self) -> dict:
        """Checks connection status."""
        url = f"{self.base_url}/instance/connectionState/{self.instance}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=10)
            response.raise_for_status()
            data = response.json()
            state = data.get("instance", {}).get("state", "unknown")
            return {"status": state, "connected": state == "open"}
        except Exception as exc:
            return {"status": "error", "connected": False}
