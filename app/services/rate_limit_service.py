"""
app/services/rate_limit_service.py

Lightweight fixed-window rate limiter backed by Redis. Protects
brute-force-sensitive endpoints (QR entry guessing, admin login, AI
assistant abuse) without adding an external dependency beyond the
Redis instance already provisioned for the platform.

Fails OPEN (allows the request) if Redis is unreachable, so a Redis
outage never takes down the whole app - this is a deliberate
trade-off: availability over strict rate enforcement.
"""

from dataclasses import dataclass

from app.infrastructure.cache.redis_client import redis_client
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


def check_rate_limit(key: str, limit: int, window_seconds: int) -> RateLimitResult:
    """
    Fixed-window counter: increments a Redis key with a TTL. The
    first hit in a window sets the expiry; subsequent hits just
    increment. Once the counter exceeds `limit` within
    `window_seconds`, further requests are rejected until the window
    resets (TTL runs out).
    """
    redis_key = f"ratelimit:{key}"

    try:
        pipe = redis_client.pipeline()
        pipe.incr(redis_key, 1)
        pipe.ttl(redis_key)
        count, ttl = pipe.execute()

        if ttl == -1:
            redis_client.expire(redis_key, window_seconds)
            ttl = window_seconds

        if count > limit:
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(ttl, 1))

        return RateLimitResult(allowed=True, remaining=max(limit - count, 0), retry_after_seconds=ttl)

    except Exception as exc:
        logger.warning(f"[RateLimit] Redis unavailable, failing open: {exc!r}")
        return RateLimitResult(allowed=True, remaining=limit, retry_after_seconds=0)