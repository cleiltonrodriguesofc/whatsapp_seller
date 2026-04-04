from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance for the entire application
limiter = Limiter(key_func=get_remote_address)
