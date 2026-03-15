from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities import Product, Campaign

class ProductRepository(ABC):
    @abstractmethod
    def save(self, product: Product) -> Product:
        pass

    @abstractmethod
    def get_by_id(self, product_id: int) -> Optional[Product]:
        pass

    @abstractmethod
    def list_all(self) -> List[Product]:
        pass

class CampaignRepository(ABC):
    @abstractmethod
    def save(self, campaign: Campaign) -> Campaign:
        pass

    @abstractmethod
    def get_by_id(self, campaign_id: int) -> Optional[Campaign]:
        pass

    @abstractmethod
    def list_all(self) -> List[Campaign]:
        pass

    @abstractmethod
    def list_pending(self) -> List[Campaign]:
        pass
