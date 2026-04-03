from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities import User, Product, Campaign, StatusCampaign, BroadcastList, BroadcastCampaign, ActivityLog


class ProductRepository(ABC):
    @abstractmethod
    def save(self, product: Product) -> Product:
        pass

    @abstractmethod
    def get_by_id(self, product_id: int, user_id: Optional[int] = None) -> Optional[Product]:
        pass

    @abstractmethod
    def list_all(self, user_id: Optional[int] = None) -> List[Product]:
        pass


class CampaignRepository(ABC):
    @abstractmethod
    def save(self, campaign: Campaign) -> Campaign:
        pass

    @abstractmethod
    def get_by_id(self, campaign_id: int, user_id: Optional[int] = None) -> Optional[Campaign]:
        pass

    @abstractmethod
    def list_all(self, user_id: Optional[int] = None) -> List[Campaign]:
        pass

    @abstractmethod
    def list_pending(self, user_id: Optional[int] = None) -> List[Campaign]:
        pass


class StatusCampaignRepository(ABC):
    @abstractmethod
    def save(self, campaign: StatusCampaign) -> StatusCampaign:
        pass

    @abstractmethod
    def get_by_id(self, campaign_id: int, user_id: Optional[int] = None) -> Optional[StatusCampaign]:
        pass

    @abstractmethod
    def list_all(self, user_id: Optional[int] = None) -> List[StatusCampaign]:
        pass

    @abstractmethod
    def list_pending(self, user_id: Optional[int] = None) -> List[StatusCampaign]:
        pass

    @abstractmethod
    def delete(self, campaign_id: int, user_id: Optional[int] = None) -> bool:
        pass


class BroadcastListRepository(ABC):
    @abstractmethod
    def save(self, broadcast_list: BroadcastList) -> BroadcastList:
        pass

    @abstractmethod
    def get_by_id(self, list_id: int, user_id: Optional[int] = None) -> Optional[BroadcastList]:
        pass

    @abstractmethod
    def list_all(self, user_id: Optional[int] = None) -> List[BroadcastList]:
        pass

    @abstractmethod
    def delete(self, list_id: int, user_id: int) -> bool:
        pass

    @abstractmethod
    def set_members(self, list_id: int, members: List[dict]) -> None:
        pass

    @abstractmethod
    def get_member_jids(self, list_id: int) -> List[str]:
        pass


class BroadcastCampaignRepository(ABC):
    @abstractmethod
    def save(self, campaign: BroadcastCampaign) -> BroadcastCampaign:
        pass

    @abstractmethod
    def get_by_id(self, campaign_id: int, user_id: int) -> Optional[BroadcastCampaign]:
        pass

    @abstractmethod
    def list_all(self, user_id: int) -> List[BroadcastCampaign]:
        pass

    @abstractmethod
    def list_due(self) -> List[BroadcastCampaign]:
        pass

    @abstractmethod
    def delete(self, campaign_id: int, user_id: int) -> bool:
        pass


class UserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def save(self, user: User) -> User:
        pass

    @abstractmethod
    def list_all(self, limit: int = 100) -> List[User]:
        pass

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        pass


class ActivityRepository(ABC):
    @abstractmethod
    def save(self, activity: ActivityLog) -> ActivityLog:
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, user_id: Optional[int] = None) -> List[ActivityLog]:
        pass
