import os
import requests  # type: ignore
import logging

from core.application.interfaces import NotificationService

logger = logging.getLogger(__name__)


class EvolutionWhatsAppService(NotificationService):
    """
    Sends WhatsApp messages via a self-hosted Evolution API instance.
    No external paid accounts needed — you scan a QR code once to link
    your own WhatsApp number. All subsequent sends are free.

    Docs: https://doc.evolution-api.com
    """

    def __init__(self):
        self.base_url = os.environ.get("EVOLUTION_API_URL", "http://evolution-api:8080")
        self.api_key = os.environ.get("EVOLUTION_API_KEY", "changeme")
        self.instance = os.environ.get("EVOLUTION_INSTANCE", "grupo_1000")

    def _headers(self) -> dict:
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    def _clean_phone(self, phone: str) -> str:
        """
        Strips formatting characters from phone numbers so the API always
        receives a raw digit string like 5598988884099.
        """
        digits = "".join(filter(str.isdigit, phone))
        # ensure country code (brazil = 55) is present
        if not digits.startswith("55"):
            digits = "55" + digits
        return digits

    def send_text(self, phone: str, message: str) -> bool:
        """
        Sends a text message to the given phone number or Group JID.
        """
        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {
            "number": self._clean_phone(phone) if "@" not in phone else phone,
            "text": message,
            "linkPreview": False,
        }
        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=10)
            logger.info("Evolution API Response Status: %s", response.status_code)
            if response.status_code >= 400:
                logger.error("Evolution API Error Response: %s", response.text)
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.error("evolution-api send failed: %s", exc)
            if "response" in locals():
                logger.error("Full response: %s", response.text)
            return False

    def send_group_text(self, group_jid: str, message: str) -> bool:
        """
        Wrapper for sending to a group JID (e.g. 123456789@g.us).
        """
        return self.send_text(group_jid, message)

    def send_group_closing_announcement(
        self, group_jid: str, month: int, winner_name: str, amount: float
    ) -> bool:
        message = (
            f"📢 *FECHAMENTO DO MÊS {month}* 📢\n\n"
            f"Olá grupo! Todos os aportes deste mês foram confirmados. ✅\n\n"
            f"🎊 O grande sorteado do mês é: *{winner_name}*!\n"
            f"💰 *Valor do Prêmio:* R$ {amount:.2f}\n\n"
            f"Parabéns! O próximo ciclo começa em breve. 🚀"
        )
        return self.send_group_text(group_jid, message)

    def get_contacts(self) -> list:
        """
        Fetches the list of private chats/contacts.
        """
        url = f"{self.base_url}/chat/fetchAllChats/{self.instance}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp contacts: %s", exc)
            return []

    def get_groups(self) -> list:
        """
        Fetches the list of groups the instance is part of.
        We disable participants fetching for speed.
        """
        url = f"{self.base_url}/group/fetchAllGroups/{self.instance}?getParticipants=false"
        try:
            response = requests.get(url, headers=self._headers(), timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp groups: %s", exc)
            return []

    def send_payment_reminder(self, name: str, phone: str, month: int, amount: float) -> bool:
        message = (
            f"Olá, *{name}*! 👋\n\n"
            f"Lembrando que o aporte do *Mês {month}* do nosso grupo ainda está "
            f"pendente.\n\n"
            f"💰 *Valor:* R$ {amount:.2f}\n\n"
            f"Efetue o pagamento o quanto antes para não perder sua participação. Obrigado! 🤝"
        )
        return self.send_text(phone, message)

    def send_prize_notification(self, name: str, phone: str, month: int, amount: float) -> bool:
        message = (
            f"🎉 Parabéns, *{name}*!\n\n"
            f"Você foi o sortudo do *Mês {month}*!\n\n"
            f"💸 *Prêmio:* R$ {amount:.2f}\n\n"
            f"O valor será transferido em breve. Bom proveite! 🎊"
        )
        return self.send_text(phone, message)

    def get_status(self) -> dict:
        """
        Checks the instance connection status.
        If it returns 404, it means the instance doesn't exist, so we treat as disconnected.
        """
        url = f"{self.base_url}/instance/connectionState/{self.instance}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=10)
            if response.status_code == 404:
                return {"status": "not_found", "connected": False}
            response.raise_for_status()
            data = response.json()
            state = data.get("instance", {}).get("state", "unknown")
            return {"status": state, "connected": state == "open"}
        except Exception as exc:
            logger.error("Failed to get WhatsApp status: %s", exc)
            return {"status": "error", "connected": False}

    def _ensure_instance_exists(self) -> bool:
        """
        Attempts to create the instance if it does not exist.
        """
        logger.info(f"Ensuring instance {self.instance} exists...")
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        try:
            # First check if it exists via fetchInstances or just try to create
            # Creating an existing instance name in Evolution API returns 403 or similar
            response = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            if response.status_code in [201, 200, 403]: # 403 usually means already exists
                return True
            return False
        except Exception as exc:
            logger.error("Failed to ensure WhatsApp instance exists: %s", exc)
            return False

    def get_qrcode(self) -> str:
        """
        Requests a QR code for pairing the instance.
        If it returns 404, attempts to create the instance first.
        """
        url = f"{self.base_url}/instance/connect/{self.instance}?base64=true"
        try:
            response = requests.get(url, headers=self._headers(), timeout=15)
            if response.status_code == 404:
                if self._ensure_instance_exists():
                    # Retry once
                    response = requests.get(url, headers=self._headers(), timeout=15)
                else:
                    return ""
            
            response.raise_for_status()
            data = response.json()
            return data.get("base64", "")
        except Exception as exc:
            logger.error("Failed to fetch WhatsApp QR Code: %s", exc)
            return ""

    def disconnect_instance(self) -> bool:
        """
        Logs out and disconnects the WhatsApp instance.
        """
        url = f"{self.base_url}/instance/logout/{self.instance}"
        try:
            response = requests.delete(url, headers=self._headers(), timeout=10)
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Failed to disconnect WhatsApp: %s", exc)
            return False
