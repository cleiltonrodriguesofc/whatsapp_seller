from core.infrastructure.utils.timezone import now_sp
from datetime import timedelta

now = now_sp()
print(f"Current SP Time: {now}")
print(f"Timezone: {now.tzinfo}")
print(f"UTCOffset: {now.utcoffset()}")

# Check if offset is -3 hours (10800 seconds) or -2 hours during DST (no longer exists in Brazil)
expected_offset = timedelta(hours=-3)
if now.utcoffset() == expected_offset:
    print("SUCCESS: Timezone offset is correct (-03:00)")
else:
    print(f"WARNING: Unexpected offset {now.utcoffset()}")
