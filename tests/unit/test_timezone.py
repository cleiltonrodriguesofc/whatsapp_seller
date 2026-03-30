from datetime import datetime, timezone
from core.infrastructure.utils.timezone import now_sp, to_sp

def test_now_sp_returns_correct_timezone():
    now = now_sp()
    # It should be naive (compatible with our SQLite DateTime columns)
    assert now.tzinfo is None

def test_to_sp_converts_naive_datetime():
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)
    sp_dt = to_sp(naive_dt)
    assert sp_dt.tzinfo is None
    assert sp_dt.hour == 12

def test_to_sp_converts_aware_utc_datetime():
    utc_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    sp_dt = to_sp(utc_dt)
    # 12:00 UTC should be 09:00 SP (UTC-3)
    assert sp_dt.hour == 9
    assert sp_dt.tzinfo is None
