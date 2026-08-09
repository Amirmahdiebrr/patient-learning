"""
app/api/middleware/logging_middleware.py

Sets a fresh request_id and clears any stale per-request context
(hospital_id/department_id/patient_id/admin_id) at the start of every
request, measures request duration, logs a single summary line per
request, and echoes the request_id back as an X-Request-ID response
header so it can be correlated with client-side error reports.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging_config import get_logger
from app.core.request_context import request_id_var, reset_request_scoped_context

logger = get_logger("request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        reset_request_scoped_context()

        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                f"[Request] {request.method} {request.url.path} failed after {duration_ms}ms"
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            f"[Request] {request.method} {request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms} ip={client_ip}"
        )

        response.headers["X-Request-ID"] = request_id
        return response