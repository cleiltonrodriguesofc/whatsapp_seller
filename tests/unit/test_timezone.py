from datetime import datetime, timezone, timedelta
import pytz
from core.infrastructure.utils.timezone import now_sp, to_sp, SAO_PAULO

def test_now_sp_returns_correct_timezone():
    now = now_sp()
    assert now.tzinfo is not None
    # Offset for America/Sao_Paulo (UTC-3)
    assert now.utcoffset() == timedelta(hours=-3)

def test_to_sp_converts_naive_datetime():
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)
    sp_dt = to_sp(naive_dt)
    assert sp_dt.tzinfo is not None
    assert sp_dt.hour == 12
    assert sp_dt.utcoffset() == timedelta(hours=-3)

def test_to_sp_converts_aware_utc_datetime():
    utc_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    sp_dt = to_sp(utc_dt)
    # 12:00 UTC should be 09:00 SP (UTC-3)
    assert sp_dt.hour == 9
    assert sp_dt.utcoffset() == timedelta(hours=-3)
