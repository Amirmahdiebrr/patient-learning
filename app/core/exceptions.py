"""
app/core/exceptions.py

Application-wide custom exceptions.
"""


class AccessGateError(Exception):
    """
    Raised whenever a request to a patient-facing route arrives
    without a valid QR-derived access cookie. Caught by a global
    FastAPI exception handler that renders the "scan the hospital QR"
    landing page instead of a raw 401/403 JSON error.
    """

    def __init__(self, reason: str = "invalid_or_missing_access_cookie"):
        self.reason = reason
        super().__init__(reason)


class OnboardingNotCompletedError(Exception):
    """
    Raised when a patient-facing route that requires a completed
    onboarding questionnaire is hit before onboarding is done.
    """
    pass