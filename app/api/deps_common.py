"""
app/api/deps_common.py

Small shared helpers used across multiple admin route modules.
Extracted here to remove the _client_ip(request) duplicate that was
copy-pasted into admin_content.py, admin_hospitals.py, and
admin_users.py.
"""

from fastapi import Request


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None