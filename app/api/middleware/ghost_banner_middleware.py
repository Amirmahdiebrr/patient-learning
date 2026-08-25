# app/api/middleware/ghost_banner_middleware.py
"""
app/api/middleware/ghost_banner_middleware.py

Injects a small, fixed, unobtrusive banner into every HTML response
when the browser is carrying an active ghost-mode cookie (see
app/services/ghost_session_service.py). This is the ONLY visual cue
that distinguishes a ghost session from a real patient's - the
underlying page itself (lesson content, quiz UI, journey timeline,
assistant) is rendered by the exact same templates/routes a real
patient hits, completely unmodified.

Implemented as response-body string injection (rather than threading
an "is_ghost" flag through every single patient template/route) so
this stays a single, self-contained, easily-removable concern instead
of touching dozens of existing patient-facing files.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

from app.core.config import settings

_BANNER_HTML = """
<div style="position:fixed;bottom:0;inset-inline:0;z-index:99999;
    background:#0B3D91;color:#fff;font-family:'Vazirmatn',sans-serif;
    font-size:13px;padding:10px 18px;display:flex;align-items:center;
    justify-content:center;gap:16px;flex-wrap:wrap;
    box-shadow:0 -6px 20px rgba(0,0,0,.18);">
    <span style="display:flex;align-items:center;gap:6px;">
        <span class="material-symbols-outlined" style="font-size:18px;">visibility</span>
        حالت روح فعال است — این دقیقاً چیزی است که یک بیمار واقعی می‌بیند.
    </span>
    <a href="/admin/ghost-browser" style="color:#fff;text-decoration:underline;font-weight:700;">پنل حالت روح</a>
    <a href="/admin/ghost-sessions/exit" style="color:#FFD8D8;text-decoration:underline;font-weight:700;">خروج از حالت روح</a>
</div>
"""


class GhostBannerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        is_ghost = request.cookies.get(settings.GHOST_MODE_COOKIE_NAME) == "1"
        content_type = response.headers.get("content-type", "")

        if not is_ghost or "text/html" not in content_type:
            return response

        body_chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(body_chunks).decode("utf-8", errors="ignore")

        if "</body>" in body:
            body = body.replace("</body>", _BANNER_HTML + "</body>", 1)

        new_body = body.encode("utf-8")

        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))

        return StarletteResponse(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )