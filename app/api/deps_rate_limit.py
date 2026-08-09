"""
app/api/deps_rate_limit.py

FastAPI dependency factory for rate-limiting a route by client IP.
Each protected route gets its own key prefix + limit + window, so a
burst on one endpoint (e.g. /admin/auth/login) never affects another
(e.g. /assistant/ask).

Routes that need a non-IP key (e.g. per-email on login) should call
check_rate_limit directly inside the route instead of using this
generic dependency - see admin_auth.py for that pattern.
"""

from fastapi import Request, HTTPException, status

from app.services.rate_limit_service import check_rate_limit


def rate_limit(key_prefix: str, limit: int, window_seconds: int):
    def _check(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        result = check_rate_limit(f"{key_prefix}:{client_ip}", limit, window_seconds)

        if not result.allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="درخواست‌های شما بیش از حد مجاز است. لطفاً کمی بعد دوباره تلاش کنید.",
                headers={"Retry-After": str(result.retry_after_seconds)},
            )

    return _check