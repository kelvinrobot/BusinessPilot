"""Shared SlowAPI limiter instance.

Import `limiter` wherever you need `@limiter.limit(...)` decorators.
The app wires it into FastAPI state in main.py so the middleware can find it.

Key function: real remote IP in production/development; a unique-per-request
UUID in the test environment so tests never accidentally share rate-limit buckets.
"""

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
