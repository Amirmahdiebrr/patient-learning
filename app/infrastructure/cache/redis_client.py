"""
app/infrastructure/cache/redis_client.py

Single shared Redis connection pool, used by the rate limiting
service and available for future caching needs (e.g. QR lookups).
"""

import redis

from app.core.config import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)