from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum
from core.infrastructure.utils.timezone import now_sp


class MessageType(Enum):
    RECEIVED = "received"
    SENT = "sent"


class SaleStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Product:
    name: str
    description: str
    price: float
    affiliate_link: str
    user_id: Optional[int] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    click_count: int = 0
    is_active: bool = True
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class Contact:
    phone_number: str
    name: Optional[str] = None
    is_allowed: bool = True
    persona_prompt: Optional[str] = None
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class Group:
    group_id: str
    name: str
    is_allowed: bool = True
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class Conversation:
    contact: Contact
    status: str = "active"
    started_at: datetime = field(default_factory=now_sp)
    closed_at: Optional[datetime] = None


@dataclass
class Message:
    conversation: Conversation
    message_type: MessageType
    content: str
    product: Optional[Product] = None
    timestamp: datetime = field(default_factory=now_sp)


@dataclass
class Sale:
    conversation: Conversation
    product: Product
    quantity: int
    total_price: float
    status: SaleStatus = SaleStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)


class CampaignStatus(Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class Campaign:
    title: str
    product: Product
    target_groups: List[str]  # List of Group JIDs
    scheduled_at: datetime
    user_id: Optional[int] = None
    instance_id: Optional[int] = None  # Specific WhatsApp instance
    status: CampaignStatus = CampaignStatus.PENDING
    custom_message: Optional[str] = None
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_sp)
    sent_at: Optional[datetime] = None

    # Recurring Scheduling
    is_recurring: bool = False
    recurrence_days: Optional[str] = None  # Comma separated "mon,tue"
    send_time: Optional[str] = None  # "HH:MM"
    last_run_at: Optional[datetime] = None
    is_ai_generated: bool = False

    # Granular Scheduling Config (v3)
    # Format: {"status": "07:00", "groups": ["09:00", "15:00"], "contacts": "once_per_day"}
    target_config: Optional[dict] = field(default_factory=dict)


@dataclass
class StatusCampaign:
    title: str
    scheduled_at: datetime
    image_url: Optional[str] = None
    background_color: Optional[str] = "#128C7E"
    caption: Optional[str] = None
    link: Optional[str] = None
    price: Optional[float] = None
    target_contacts: List[str] = field(default_factory=list)  # Empty means allContacts=True
    user_id: Optional[int] = None
    instance_id: Optional[int] = None
    status: CampaignStatus = CampaignStatus.PENDING
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_sp)
    sent_at: Optional[datetime] = None

    # Recurring Scheduling
    is_recurring: bool = False
    recurrence_days: Optional[str] = None
    send_time: Optional[str] = None
    last_run_at: Optional[datetime] = None


@dataclass
class User:
    email: str
    hashed_password: str
    id: Optional[int] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class Instance:
    user_id: int
    name: str
    apikey: Optional[str] = None
    status: str = "disconnected"
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class BroadcastList:
    user_id: int
    name: str
    description: Optional[str] = None
    id: Optional[int] = None
    member_count: int = 0
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class BroadcastListMember:
    list_id: int
    target_jid: str
    target_name: str
    target_type: str  # 'chat' | 'group'
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_sp)


@dataclass
class BroadcastCampaign:
    user_id: int
    instance_id: int
    title: str
    target_type: str  # 'contacts' | 'groups' | 'list'
    message: str
    target_jids: List[str] = field(default_factory=list)
    list_id: Optional[int] = None
    image_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_days: Optional[str] = None
    send_time: Optional[str] = None
    last_run_at: Optional[datetime] = None
    status: str = "draft"
    sent_at: Optional[datetime] = None
    total_targets: int = 0
    sent_count: int = 0
    failed_count: int = 0
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_sp)
