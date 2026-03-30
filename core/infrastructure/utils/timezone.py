import pytz
from datetime import datetime

# Central Timezone definitions
SAO_PAULO = pytz.timezone("America/Sao_Paulo")

def now_sp() -> datetime:
    """
    Returns current naive datetime in America/Sao_Paulo timezone.
    """
    return datetime.now(SAO_PAULO).replace(tzinfo=None)

def to_sp(dt: datetime) -> datetime:
    """
    Converts a datetime to a naive America/Sao_Paulo datetime.
    """
    if dt.tzinfo:
        return dt.astimezone(SAO_PAULO).replace(tzinfo=None)
    return dt
