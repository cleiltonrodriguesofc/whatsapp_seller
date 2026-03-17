from typing import List, Optional
from sqlalchemy.orm import Session
from core.application.repositories import ProductRepository, CampaignRepository
from core.domain.entities import (
    Product,
    Campaign,
    CampaignStatus as DomainCampaignStatus,
)
from core.infrastructure.database.models import (
    ProductModel,
    CampaignModel,
    WhatsAppTargetModel,
    UserModel,
    InstanceModel,
    CampaignStatus as ModelCampaignStatus,
)
from sqlalchemy import select
from datetime import datetime


class SQLProductRepository(ProductRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, product: Product) -> Product:
        model = ProductModel(
            name=product.name,
            description=product.description,
            price=product.price,
            affiliate_link=product.affiliate_link,
            image_url=product.image_url,
            category=product.category,
            is_active=product.is_active,
            user_id=product.user_id,  # Add user_id
        )
        if product.id:
            model.id = product.id
            self.db.merge(model)
        else:
            self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        product.id = model.id
        return product

    def get_by_id(
        self, product_id: int, user_id: Optional[int] = None
    ) -> Optional[Product]:
        query = self.db.query(ProductModel).filter(ProductModel.id == product_id)
        if user_id:
            query = query.filter(ProductModel.user_id == user_id)
        model = query.first()
        if not model:
            return None
        return self._to_entity(model)

    def list_all(self, user_id: Optional[int] = None) -> List[Product]:
        query = self.db.query(ProductModel)
        if user_id:
            query = query.filter(ProductModel.user_id == user_id)
        models = query.all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: ProductModel) -> Product:
        return Product(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            description=model.description,
            price=model.price,
            affiliate_link=model.affiliate_link,
            image_url=model.image_url,
            category=model.category,
            is_active=model.is_active,
            created_at=model.created_at,
        )


import json


class SQLCampaignRepository(CampaignRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, campaign: Campaign) -> Campaign:
        model = CampaignModel(
            title=campaign.title,
            user_id=campaign.user_id,
            product_id=campaign.product.id,
            scheduled_at=campaign.scheduled_at,
            status=ModelCampaignStatus[campaign.status.name],
            custom_message=campaign.custom_message,
            is_recurring=getattr(campaign, "is_recurring", False),
            recurrence_days=getattr(campaign, "recurrence_days", None),
            send_time=getattr(campaign, "send_time", None),
            target_config=(
                json.dumps(campaign.target_config) if campaign.target_config else None
            ),
        )
        if campaign.id:
            model.id = campaign.id
            self.db.merge(model)
        else:
            self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        campaign.id = model.id
        return campaign

    def get_by_id(
        self, campaign_id: int, user_id: Optional[int] = None
    ) -> Optional[Campaign]:
        query = self.db.query(CampaignModel).filter(CampaignModel.id == campaign_id)
        if user_id:
            query = query.filter(CampaignModel.user_id == user_id)
        model = query.first()
        if not model:
            return None
        return self._to_entity(model)

    def list_all(self, user_id: Optional[int] = None) -> List[Campaign]:
        query = self.db.query(CampaignModel)
        if user_id:
            query = query.filter(CampaignModel.user_id == user_id)
        models = query.all()
        return [self._to_entity(m) for m in models]

    def list_pending(self, user_id: Optional[int] = None) -> List[Campaign]:
        query = self.db.query(CampaignModel).filter(
            CampaignModel.status == ModelCampaignStatus.SCHEDULED
        )
        if user_id:
            query = query.filter(CampaignModel.user_id == user_id)
        models = query.all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: CampaignModel) -> Campaign:
        # Assuming product relationship is loaded
        from core.infrastructure.database.repositories import SQLProductRepository

        product_repo = SQLProductRepository(self.db)
        product = product_repo.get_by_id(model.product_id)

        campaign_entity = Campaign(
            id=model.id,
            user_id=model.user_id,
            title=model.title,
            product=product,
            target_groups=[],  # This would need a separate fetch or relationship
            scheduled_at=model.scheduled_at,
            status=DomainCampaignStatus[model.status.name],
            custom_message=model.custom_message,
            created_at=model.created_at,
            sent_at=model.sent_at,
        )

        # Add recurring fields to entity if they exist
        campaign_entity.is_recurring = model.is_recurring
        campaign_entity.recurrence_days = model.recurrence_days
        campaign_entity.send_time = model.send_time
        campaign_entity.last_run_at = model.last_run_at

        if model.target_config:
            try:
                campaign_entity.target_config = json.loads(model.target_config)
            except:
                campaign_entity.target_config = {}

        return campaign_entity


class SQLTargetRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_sync(self, targets: List[dict], user_id: int):
        """
        Syncs a list of targets from the API, preventing duplicates for a specific user.
        """
        now = datetime.utcnow()
        for t in targets:
            existing = (
                self.db.query(WhatsAppTargetModel)
                .filter(
                    WhatsAppTargetModel.jid == t["id"],
                    WhatsAppTargetModel.user_id == user_id,
                )
                .first()
            )
            if existing:
                existing.name = t["subject"]
                existing.type = "group" if "@g.us" in t["id"] else "chat"
                existing.last_synced_at = now
                existing.is_active = True
            else:
                new_target = WhatsAppTargetModel(
                    user_id=user_id,
                    jid=t["id"],
                    name=t["subject"],
                    type="group" if "@g.us" in t["id"] else "chat",
                    last_synced_at=now,
                )
                self.db.add(new_target)
        self.db.commit()

    def list_all(self, user_id: int):
        return (
            self.db.query(WhatsAppTargetModel)
            .filter(
                WhatsAppTargetModel.is_active == True,
                WhatsAppTargetModel.user_id == user_id,
            )
            .all()
        )


class SQLUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[UserModel]:
        return self.db.query(UserModel).filter(UserModel.email == email).first()

    def save(self, user: UserModel) -> UserModel:
        if user.id:
            self.db.merge(user)
        else:
            self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


class SQLInstanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> List[InstanceModel]:
        return (
            self.db.query(InstanceModel).filter(InstanceModel.user_id == user_id).all()
        )

    def save(self, instance: InstanceModel) -> InstanceModel:
        if instance.id:
            self.db.merge(instance)
        else:
            self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
