import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from core.application.repositories import (
    ProductRepository,
    CampaignRepository,
    StatusCampaignRepository,
)
from core.domain.entities import (
    Product,
    Campaign,
    StatusCampaign,
    StatusItem,
    CampaignStatus as DomainCampaignStatus,
    StatusCampaignStatus as DomainStatusCampaignStatus,
)
from core.infrastructure.database.models import (
    ProductModel,
    CampaignModel,
    StatusCampaignModel,
    StatusItemModel,
    WhatsAppTargetModel,
    UserModel,
    InstanceModel,
    CampaignStatus as ModelCampaignStatus,
    StatusCampaignStatus as ModelStatusCampaignStatus,
    campaign_groups,
)

logger = logging.getLogger(__name__)


class SQLProductRepository(ProductRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, product: Product) -> Product:
        if product.id:
            model = (
                self.db.query(ProductModel)
                .filter(ProductModel.id == product.id)
                .first()
            )
            if model:
                model.name = product.name
                model.description = product.description
                model.price = product.price
                model.affiliate_link = product.affiliate_link
                model.image_url = product.image_url
                model.category = product.category
                model.click_count = product.click_count
                model.is_active = product.is_active
            else:
                model = ProductModel(
                    name=product.name,
                    description=product.description,
                    price=product.price,
                    affiliate_link=product.affiliate_link,
                    image_url=product.image_url,
                    category=product.category,
                    click_count=product.click_count,
                    is_active=product.is_active,
                    user_id=product.user_id,
                )
                self.db.add(model)
        else:
            model = ProductModel(
                name=product.name,
                description=product.description,
                price=product.price,
                affiliate_link=product.affiliate_link,
                image_url=product.image_url,
                category=product.category,
                click_count=product.click_count,
                is_active=product.is_active,
                user_id=product.user_id,
            )
            self.db.add(model)

        self.db.commit()
        self.db.refresh(model)
        product.id = model.id
        return product

    def delete(self, product_id: int, user_id: int) -> bool:
        model = (
            self.db.query(ProductModel)
            .filter(ProductModel.id == product_id, ProductModel.user_id == user_id)
            .first()
        )
        if model:
            # Soft delete: mark as inactive to prevent FK violations in campaigns
            model.is_active = False
            self.db.commit()
            return True
        return False

    def get_by_id(
        self, product_id: int, user_id: Optional[int] = None
    ) -> Optional[Product]:
        query = self.db.query(ProductModel).filter(
            ProductModel.id == product_id, ProductModel.is_active
        )
        if user_id:
            query = query.filter(ProductModel.user_id == user_id)
        model = query.first()
        if not model:
            return None
        return self._to_entity(model)

    def list_all(self, user_id: Optional[int] = None) -> List[Product]:
        query = self.db.query(ProductModel).filter(ProductModel.is_active)
        if user_id:
            query = query.filter(ProductModel.user_id == user_id)
        models = query.all()
        return [self._to_entity(m) for m in models]

    def increment_clicks(self, product_id: int):
        from sqlalchemy import update, func
        try:
            # use coalesce to handle NULL values if they exist
            self.db.execute(
                update(ProductModel)
                .where(ProductModel.id == product_id)
                .values(click_count=func.coalesce(ProductModel.click_count, 0) + 1)
            )
            self.db.commit()
            print(f"DEBUG: Incremented clicks for product {product_id}")
        except Exception as e:
            self.db.rollback()
            print(f"DEBUG: Failed to increment clicks: {e}")

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
            click_count=model.click_count,
            is_active=model.is_active,
            created_at=model.created_at,
        )




class SQLCampaignRepository(CampaignRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, campaign: Campaign) -> Campaign:
        if campaign.id:
            model = (
                self.db.query(CampaignModel)
                .filter(CampaignModel.id == campaign.id)
                .first()
            )
            if model:
                model.title = campaign.title
                model.product_id = campaign.product.id
                model.instance_id = campaign.instance_id
                model.scheduled_at = campaign.scheduled_at
                model.status = ModelCampaignStatus[campaign.status.name]
                model.custom_message = campaign.custom_message
                model.is_recurring = campaign.is_recurring
                model.recurrence_days = campaign.recurrence_days
                model.send_time = campaign.send_time
                model.is_ai_generated = campaign.is_ai_generated
                model.sent_at = campaign.sent_at
                model.target_config = (
                    json.dumps(campaign.target_config)
                    if campaign.target_config
                    else None
                )
                
                # Sync target groups (association table)
                if campaign.target_groups is not None:
                    # Clear existing and add new
                    self.db.execute(
                        campaign_groups.delete().where(
                            campaign_groups.c.campaign_id == model.id
                        )
                    )
                    for jid in campaign.target_groups:
                        self.db.execute(
                            campaign_groups.insert().values(
                                campaign_id=model.id, group_jid=jid
                            )
                        )
            else:
                model = CampaignModel(
                    title=campaign.title,
                    user_id=campaign.user_id,
                    product_id=campaign.product.id,
                    instance_id=campaign.instance_id,
                    scheduled_at=campaign.scheduled_at,
                    status=ModelCampaignStatus[campaign.status.name],
                    custom_message=campaign.custom_message,
                    is_recurring=campaign.is_recurring,
                    recurrence_days=campaign.recurrence_days,
                    send_time=campaign.send_time,
                    is_ai_generated=campaign.is_ai_generated,
                    target_config=(
                        json.dumps(campaign.target_config)
                        if campaign.target_config
                        else None
                    ),
                )
                self.db.add(model)
                self.db.flush()  # Get ID

                # Sync target groups
                if campaign.target_groups:
                    for jid in campaign.target_groups:
                        self.db.execute(
                            campaign_groups.insert().values(
                                campaign_id=model.id, group_jid=jid
                            )
                        )
        else:
            model = CampaignModel(
                title=campaign.title,
                user_id=campaign.user_id,
                product_id=campaign.product.id,
                instance_id=campaign.instance_id,
                scheduled_at=campaign.scheduled_at,
                status=ModelCampaignStatus[campaign.status.name],
                custom_message=campaign.custom_message,
                is_recurring=campaign.is_recurring,
                recurrence_days=campaign.recurrence_days,
                send_time=campaign.send_time,
                is_ai_generated=campaign.is_ai_generated,
                target_config=(
                    json.dumps(campaign.target_config)
                    if campaign.target_config
                    else None
                ),
            )
            self.db.add(model)
            self.db.flush()

            # Sync target groups
            if campaign.target_groups:
                for jid in campaign.target_groups:
                    self.db.execute(
                        campaign_groups.insert().values(
                            campaign_id=model.id, group_jid=jid
                        )
                    )

        self.db.commit()
        self.db.refresh(model)
        campaign.id = model.id
        return campaign

    def delete(self, campaign_id: int, user_id: int) -> bool:
        model = (
            self.db.query(CampaignModel)
            .filter(CampaignModel.id == campaign_id, CampaignModel.user_id == user_id)
            .first()
        )
        if model:
            # remove association table rows first to avoid fk violation
            self.db.execute(
                campaign_groups.delete().where(
                    campaign_groups.c.campaign_id == model.id
                )
            )
            self.db.delete(model)
            self.db.commit()
            return True
        return False

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

        # Load target groups from association table
        target_jids = [
            r[0]
            for r in self.db.query(campaign_groups.c.group_jid)
            .filter(campaign_groups.c.campaign_id == model.id)
            .all()
        ]

        campaign_entity = Campaign(
            id=model.id,
            user_id=model.user_id,
            instance_id=model.instance_id,
            title=model.title,
            product=product,
            target_groups=target_jids,
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
        campaign_entity.is_ai_generated = model.is_ai_generated

        if model.target_config:
            try:
                campaign_entity.target_config = json.loads(model.target_config)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("failed to deserialise target_config for campaign %s: %s", model.id, exc)
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
                WhatsAppTargetModel.is_active,
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


class SQLStatusCampaignRepository(StatusCampaignRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, campaign: StatusCampaign) -> StatusCampaign:
        if campaign.id:
            model = (
                self.db.query(StatusCampaignModel)
                .filter(StatusCampaignModel.id == campaign.id)
                .first()
            )
            if model:
                model.title = campaign.title
                model.instance_id = campaign.instance_id
                model.scheduled_at = campaign.scheduled_at
                model.status = ModelStatusCampaignStatus[campaign.status.name]
                model.is_recurring = campaign.is_recurring
                model.recurrence_days = campaign.recurrence_days
                model.send_time = campaign.send_time
                model.sent_at = campaign.sent_at

                # Sync items (simple delete/re-add)
                self.db.query(StatusItemModel).filter(
                    StatusItemModel.campaign_id == model.id
                ).delete()
                for idx, item in enumerate(campaign.items):
                    item_model = StatusItemModel(
                        campaign_id=model.id,
                        image_url=item.image_url,
                        caption=item.caption,
                        link=item.link,
                        price=item.price,
                        position=idx,
                    )
                    self.db.add(item_model)
        else:
            model = StatusCampaignModel(
                title=campaign.title,
                user_id=campaign.user_id,
                instance_id=campaign.instance_id,
                scheduled_at=campaign.scheduled_at,
                status=ModelStatusCampaignStatus[campaign.status.name],
                is_recurring=campaign.is_recurring,
                recurrence_days=campaign.recurrence_days,
                send_time=campaign.send_time,
            )
            self.db.add(model)
            self.db.flush()

            for idx, item in enumerate(campaign.items):
                item_model = StatusItemModel(
                    campaign_id=model.id,
                    image_url=item.image_url,
                    caption=item.caption,
                    link=item.link,
                    price=item.price,
                    position=idx,
                )
                self.db.add(item_model)

        self.db.commit()
        self.db.refresh(model)
        campaign.id = model.id
        # Update IDs in items from models
        items_models = (
            self.db.query(StatusItemModel)
            .filter(StatusItemModel.campaign_id == model.id)
            .order_by(StatusItemModel.position)
            .all()
        )
        for i, m in enumerate(items_models):
            if i < len(campaign.items):
                campaign.items[i].id = m.id

        return campaign

    def get_by_id(
        self, campaign_id: int, user_id: Optional[int] = None
    ) -> Optional[StatusCampaign]:
        query = self.db.query(StatusCampaignModel).filter(
            StatusCampaignModel.id == campaign_id
        )
        if user_id:
            query = query.filter(StatusCampaignModel.user_id == user_id)
        model = query.first()
        if not model:
            return None
        return self._to_entity(model)

    def list_all(self, user_id: Optional[int] = None) -> List[StatusCampaign]:
        query = self.db.query(StatusCampaignModel)
        if user_id:
            query = query.filter(StatusCampaignModel.user_id == user_id)
        models = query.all()
        return [self._to_entity(m) for m in models]

    def delete(self, campaign_id: int, user_id: int) -> bool:
        model = (
            self.db.query(StatusCampaignModel)
            .filter(
                StatusCampaignModel.id == campaign_id,
                StatusCampaignModel.user_id == user_id,
            )
            .first()
        )
        if model:
            self.db.delete(model)
            self.db.commit()
            return True
        return False

    def _to_entity(self, model: StatusCampaignModel) -> StatusCampaign:
        items = [
            StatusItem(
                id=item.id,
                image_url=item.image_url,
                caption=item.caption,
                link=item.link,
                price=item.price,
            )
            for item in sorted(model.items, key=lambda x: x.position)
        ]

        return StatusCampaign(
            id=model.id,
            user_id=model.user_id,
            instance_id=model.instance_id,
            title=model.title,
            items=items,
            scheduled_at=model.scheduled_at,
            is_recurring=model.is_recurring,
            recurrence_days=model.recurrence_days,
            send_time=model.send_time,
            status=DomainStatusCampaignStatus[model.status.name],
            created_at=model.created_at,
            sent_at=model.sent_at,
        )
