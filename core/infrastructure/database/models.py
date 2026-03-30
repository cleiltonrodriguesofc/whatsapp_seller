from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Enum as SQLEnum,
    ForeignKey,
    Table,
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from core.infrastructure.utils.timezone import now_sp
import enum

Base = declarative_base()


class CampaignStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


# Association table for Campaign - Group
campaign_groups = Table(
    "campaign_groups",
    Base.metadata,
    Column("campaign_id", Integer, ForeignKey("campaigns.id")),
    Column("group_jid", String),
)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_sp)

    products = relationship("ProductModel", back_populates="user")
    instances = relationship("InstanceModel", back_populates="user")


class InstanceModel(Base):
    __tablename__ = "instances"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, unique=True, nullable=False)  # Evolution instance name
    display_name = Column(String, nullable=True)  # User custom friendly name
    apikey = Column(String, nullable=True)  # Specific instance apikey if different
    status = Column(String, default="disconnected")
    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel", back_populates="instances")


class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    affiliate_link = Column(String)
    image_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel", back_populates="products")


class WhatsAppTargetModel(Base):
    __tablename__ = "whatsapp_targets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    jid = Column(String, unique=False, index=True, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    type = Column(String)  # 'group' or 'chat'
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, default=now_sp)


class CampaignModel(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    title = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))
    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=True)  # Link to specific instance
    scheduled_at = Column(DateTime)
    status = Column(String, default="pending", index=True)
    custom_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_sp)
    sent_at = Column(DateTime, nullable=True)

    # Recurring Scheduling (Alarm style)
    is_recurring = Column(Boolean, default=False, index=True)
    recurrence_days = Column(String, nullable=True)  # "mon,tue,wed,thu,fri,sat,sun"
    send_time = Column(String, nullable=True)  # "HH:MM"
    last_run_at = Column(DateTime, nullable=True)  # To prevent double-send in the same day
    target_config = Column(
        Text, nullable=True
    )  # JSON stored as string: {"status": "07:00", "groups": ["08:00", "12:00"]}
    is_ai_generated = Column(Boolean, default=False)

    product = relationship("ProductModel")
    instance = relationship("InstanceModel")
    target_groups = relationship(
        "WhatsAppTargetModel",
        secondary=campaign_groups,
        primaryjoin="CampaignModel.id == campaign_groups.c.campaign_id",
        secondaryjoin="WhatsAppTargetModel.jid == campaign_groups.c.group_jid",
        viewonly=True,
    )


class StatusCampaignModel(Base):
    __tablename__ = "status_campaigns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    background_color = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    link = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=True)
    scheduled_at = Column(DateTime)
    status = Column(String, default="pending", index=True)
    target_contacts = Column(Text, nullable=True)  # JSON or comma-separated list of jids
    created_at = Column(DateTime, default=now_sp)
    sent_at = Column(DateTime, nullable=True)

    # Recurring Scheduling
    is_recurring = Column(Boolean, default=False, index=True)
    recurrence_days = Column(String, nullable=True)
    send_time = Column(String, nullable=True)
    last_run_at = Column(DateTime, nullable=True)

    instance = relationship("InstanceModel")


class BroadcastListModel(Base):
    __tablename__ = "broadcast_lists"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_sp)

    members = relationship(
        "BroadcastListMemberModel", back_populates="broadcast_list", cascade="all, delete-orphan"
    )


class BroadcastListMemberModel(Base):
    __tablename__ = "broadcast_list_members"
    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("broadcast_lists.id", ondelete="CASCADE"), nullable=False)
    target_jid = Column(String, nullable=False)
    target_name = Column(String, nullable=True)
    target_type = Column(String, nullable=False)  # 'chat' | 'group'
    created_at = Column(DateTime, default=now_sp)

    broadcast_list = relationship("BroadcastListModel", back_populates="members")


class BroadcastCampaignModel(Base):
    __tablename__ = "broadcast_campaigns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=False)
    title = Column(String, nullable=False)

    # target
    target_type = Column(String, nullable=False)  # 'contacts' | 'groups' | 'list'
    target_jids = Column(Text, nullable=True)  # JSON array
    list_id = Column(Integer, ForeignKey("broadcast_lists.id", ondelete="SET NULL"), nullable=True)

    # content
    message = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)

    # scheduling
    scheduled_at = Column(DateTime, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_days = Column(String, nullable=True)
    send_time = Column(String, nullable=True)
    last_run_at = Column(DateTime, nullable=True)

    # state
    status = Column(String, default="draft")
    sent_at = Column(DateTime, nullable=True)
    total_targets = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserModel")
    instance = relationship("InstanceModel")
    broadcast_list = relationship("BroadcastListModel")
