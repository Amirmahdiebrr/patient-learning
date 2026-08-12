"""
app/core/csrf.py

Generic double-submit-cookie CSRF protection, shared by the
patient-facing HTML forms and the admin panel's AJAX calls.

The cookie is httpOnly - JS never needs to read it. For patient
forms we embed the current token straight into a hidden field when
we render the page server-side; for the admin panel we embed it into
a <meta> tag the same way. A cross-site attacker can trigger a POST
but can never read or set our cookie, so their forged request's
token can never match.
"""

import secrets

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings


def issue_csrf_cookie(response: Response, cookie_name: str, existing_token: str | None = None) -> str:
    token = existing_token or secrets.token_urlsafe(32)
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=60 * 60 * 24 * 180,
    )
    return token


def verify_csrf(request: Request, cookie_name: str, submitted_token: str | None) -> None:
    cookie_token = request.cookies.get(cookie_name)
    if not cookie_token or not submitted_token or not secrets.compare_digest(cookie_token, submitted_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "درخواست نامعتبر است (CSRF). لطفاً صفحه را رفرش کنید.")