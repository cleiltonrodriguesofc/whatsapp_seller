from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
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
    PAUSED = "paused"
    CANCELED = "canceled"


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
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_sp)
    referral_balance = Column(Float, default=0.0)
    referral_code_id = Column(Integer, ForeignKey("referral_codes.id"), nullable=True)
    agreed_to_terms_at = Column(DateTime, nullable=True)
    reset_token = Column(String, unique=True, index=True, nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)

    products = relationship("ProductModel", back_populates="user")
    instances = relationship("InstanceModel", back_populates="user")
    subscription = relationship(
        "SubscriptionModel", back_populates="user", uselist=False
    )
    referral_code = relationship("ReferralCodeModel", foreign_keys=[referral_code_id])


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
    instance_id = Column(Integer, ForeignKey("instances.id"), index=True, nullable=True)
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
    instance_id = Column(
        Integer, ForeignKey("instances.id"), nullable=True
    )  # Link to specific instance
    scheduled_at = Column(DateTime)
    status = Column(String, default="pending", index=True)
    custom_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_sp)
    sent_at = Column(DateTime, nullable=True)

    # Recurring Scheduling (Alarm style)
    is_recurring = Column(Boolean, default=False, index=True)
    recurrence_days = Column(String, nullable=True)  # "mon,tue,wed,thu,fri,sat,sun"
    send_time = Column(String, nullable=True)  # "HH:MM"
    last_run_at = Column(
        DateTime, nullable=True
    )  # To prevent double-send in the same day
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
    target_contacts = Column(
        Text, nullable=True
    )  # JSON or comma-separated list of jids
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
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    instance_id = Column(Integer, ForeignKey("instances.id"), index=True, nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_sp)

    members = relationship(
        "BroadcastListMemberModel",
        back_populates="broadcast_list",
        cascade="all, delete-orphan",
    )


class BroadcastListMemberModel(Base):
    __tablename__ = "broadcast_list_members"
    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(
        Integer, ForeignKey("broadcast_lists.id", ondelete="CASCADE"), nullable=False
    )
    target_jid = Column(String, nullable=False)
    target_name = Column(String, nullable=True)
    target_type = Column(String, nullable=False)  # 'chat' | 'group'
    created_at = Column(DateTime, default=now_sp)

    broadcast_list = relationship("BroadcastListModel", back_populates="members")


class BroadcastCampaignModel(Base):
    __tablename__ = "broadcast_campaigns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=False)
    title = Column(String, nullable=False)

    # target
    target_type = Column(String, nullable=False)  # 'contacts' | 'groups' | 'list'
    target_jids = Column(Text, nullable=True)  # JSON array
    list_id = Column(
        Integer, ForeignKey("broadcast_lists.id", ondelete="SET NULL"), nullable=True
    )

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


class PlanModel(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # "starter", "pro", "agency"
    display_name = Column(String, nullable=False)  # "Starter", "Pro", "Agência"
    price_brl = Column(Float, nullable=False)  # 97.00, 197.00, 397.00
    max_instances = Column(Integer, nullable=False)  # 1, 3, -1
    has_ai = Column(Boolean, default=False)
    mp_plan_id = Column(String, nullable=True)  # ID do plano no Mercado Pago
    created_at = Column(DateTime, default=now_sp)


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(
        String, default="trialing"
    )  # "trialing", "active", "canceled", "past_due"
    trial_ends_at = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    mp_preapproval_id = Column(
        String, nullable=True
    )  # ID da assinatura no Mercado Pago
    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel", back_populates="subscription")
    plan = relationship("PlanModel")


class ReferralCodeModel(Base):
    __tablename__ = "referral_codes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=now_sp)


class ReferralConversionModel(Base):
    __tablename__ = "referral_conversions"
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # quem indicou
    referred_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # quem se cadastrou
    status = Column(String, default="pending")  # "pending", "converted", "rewarded"
    reward_brl = Column(Float, default=0.0)
    rewarded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_sp)


class ActivityLogModel(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    event_type = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=now_sp)

    user = relationship("UserModel")


# ── birthday messaging ────────────────────────────────────────────────────────


class BirthdayContactModel(Base):
    __tablename__ = "birthday_contacts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    birth_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel")


class BirthdayTemplateModel(Base):
    __tablename__ = "birthday_templates"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # supports {nome} placeholder
    media_url = Column(String, nullable=True)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel")


class BirthdayLogModel(Base):
    __tablename__ = "birthday_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    contact_id = Column(Integer, ForeignKey("birthday_contacts.id"), nullable=True)
    recipient_name = Column(String, nullable=False)
    recipient_phone = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending", index=True)  # "pending" | "sent" | "failed"
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel")
    contact = relationship("BirthdayContactModel")

# ── affiliate configuration ───────────────────────────────────────────────────

class AffiliateConfigModel(Base):
    __tablename__ = "affiliate_configs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, unique=True)

    # ── magalu affiliate config ───────────────────────────────────────
    storefront_slug = Column(String, nullable=True)  # e.g. "cleiltontec"
    categories = Column(String, default="notebook,celular")  # comma-separated category keys
    min_discount_percent = Column(Float, default=10.0)
    max_offers_per_run = Column(Integer, default=5)
    dispatch_hours = Column(String, default="9,12,18")  # status dispatch hours
    preferred_brands = Column(String, nullable=True)

    # ── mercado livre affiliate config ────────────────────────────────
    ml_profile_slug = Column(String, nullable=True)   # e.g. "cleiltonrodriguesdossantos"
    ml_enabled = Column(Boolean, default=False)        # enable/disable ml gateway
    ml_categories = Column(String, default="notebook,celular")  # ml category keys

    # ── group broadcast config ────────────────────────────────────────
    group_enabled = Column(Boolean, default=False)     # enable group broadcast
    group_jids = Column(Text, nullable=True)           # json array of group jids to broadcast to
    group_dispatch_hours = Column(String, default="9,12,15,18,21")  # group dispatch hours

    # ── promo card customization ──────────────────────────────────────
    store_type = Column(String, default="magalu")  # magalu, generica
    theme_color = Column(String, default="#0088ff")
    tagline = Column(String, default="tem na minha loja")

    require_approval = Column(Boolean, default=False)

    # owner avatar stored as base64 in db to survive render's ephemeral filesystem
    owner_avatar_b64 = Column(Text, nullable=True)

    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel")


class AffiliateLogModel(Base):
    __tablename__ = "affiliate_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    product_title = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    original_url = Column(Text, nullable=False)
    short_url = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    old_price = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    installment_text = Column(String, nullable=True)
    pix_discount_text = Column(String, nullable=True)
    source = Column(String, default="magalu")  # "magalu" | "mercadolivre"
    status = Column(String, default="sent", index=True)  # "pending", "sent", "failed", "rejected"
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_sp)

    user = relationship("UserModel")

class ShortLinkModel(Base):
    __tablename__ = "short_links"
    id = Column(Integer, primary_key=True, index=True)
    hash_id = Column(String, unique=True, index=True, nullable=False)
    original_url = Column(Text, nullable=False)
    store_name = Column(String, nullable=False)
    clicks = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_sp)
