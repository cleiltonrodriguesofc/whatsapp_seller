from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum

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
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Contact:
    phone_number: str
    name: Optional[str] = None
    is_allowed: bool = True
    persona_prompt: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Group:
    group_id: str
    name: str
    is_allowed: bool = True
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Conversation:
    contact: Contact
    status: str = "active"
    started_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None

@dataclass
class Message:
    conversation: Conversation
    message_type: MessageType
    content: str
    product: Optional[Product] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Sale:
    conversation: Conversation
    product: Product
    quantity: int
    total_price: float
    status: SaleStatus = SaleStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

class CampaignStatus(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"

@dataclass
class Campaign:
    title: str
    product: Product
    target_groups: List[str]  # List of Group JIDs
    scheduled_at: datetime
    status: CampaignStatus = CampaignStatus.PENDING
    custom_message: Optional[str] = None
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    
    # Recurring Scheduling
    is_recurring: bool = False
    recurrence_days: Optional[str] = None  # Comma separated "mon,tue"
    send_time: Optional[str] = None  # "HH:MM"
    last_run_at: Optional[datetime] = None
