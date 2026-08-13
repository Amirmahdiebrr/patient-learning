"""
app/services/content_admin/errors.py

Framework-agnostic exceptions raised by the content-admin service
layer. Routes in app/api/v1/admin_content.py catch these and convert
them into the appropriate HTTPException - this keeps the service
layer free of any FastAPI/Starlette import, so it stays testable and
reusable outside a web request (scripts, other routers, etc).
"""


class ContentNotFoundError(Exception):
    """Raised when a referenced content-library row doesn't exist."""


class ContentConflictError(Exception):
    """Raised when an operation would violate a uniqueness/state rule."""


class ContentValidationError(Exception):
    """Raised for a request-shape problem the Pydantic schema didn't already catch."""