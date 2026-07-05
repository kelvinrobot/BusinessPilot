
import uuid

from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_limit_key(request):
    # Local import avoids circular dependency (config → rate_limit → config).
    from app.core.config import settings

    if settings.environment == "test":
        return str(uuid.uuid4())
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=[])
