from abc import ABC, abstractmethod
from typing import Optional


class NotificationService(ABC):
    """
    Interface for sending notifications via different channels (e.g., WhatsApp).
    """

    @abstractmethod
    async def send_text(self, phone: str, message: str) -> bool:
        pass

    @abstractmethod
    async def send_group_text(self, group_jid: str, message: str) -> bool:
        pass

    @abstractmethod
    async def send_group_closing_announcement(
        self, group_jid: str, month: int, winner_name: str, amount: float
    ) -> bool:
        pass

    @abstractmethod
    async def get_groups(self) -> list:
        pass

    @abstractmethod
    async def send_payment_reminder(self, name: str, phone: str, month: int, amount: float) -> bool:
        pass

    @abstractmethod
    async def send_prize_notification(self, name: str, phone: str, month: int, amount: float) -> bool:
        pass

    @abstractmethod
    async def get_status(self) -> dict:
        pass

    @abstractmethod
    async def get_qrcode(self) -> str:
        pass

    @abstractmethod
    async def delete_instance(self) -> bool:
        pass


class AIService(ABC):
    """
    Interface for AI-powered interactions.
    """

    @abstractmethod
    async def chat(self, message: str, context: Optional[str] = None) -> str:
        pass
