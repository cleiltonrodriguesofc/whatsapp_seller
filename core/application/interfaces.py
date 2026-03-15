from abc import ABC, abstractmethod
from typing import Optional, List

class NotificationService(ABC):
    """
    Interface for sending notifications via different channels (e.g., WhatsApp).
    """

    @abstractmethod
    def send_text(self, phone: str, message: str) -> bool:
        pass

    @abstractmethod
    def send_group_text(self, group_jid: str, message: str) -> bool:
        pass

    @abstractmethod
    def send_group_closing_announcement(self, group_jid: str, month: int, winner_name: str, amount: float) -> bool:
        pass

    @abstractmethod
    def get_groups(self) -> list:
        pass

    @abstractmethod
    def send_payment_reminder(self, name: str, phone: str, month: int, amount: float) -> bool:
        pass

    @abstractmethod
    def send_prize_notification(self, name: str, phone: str, month: int, amount: float) -> bool:
        pass

    @abstractmethod
    def get_status(self) -> dict:
        pass

    @abstractmethod
    def get_qrcode(self) -> str:
        pass

    @abstractmethod
    def disconnect_instance(self) -> bool:
        pass

class AIService(ABC):
    """
    Interface for AI-powered interactions.
    """

    @abstractmethod
    def chat(self, message: str, context: Optional[str] = None) -> str:
        pass
