"""
app/core/request_context.py

Per-request context values (request_id, hospital_id, department_id,
patient_id, admin_id) stored in contextvars so any log call anywhere
in the codebase can pick them up automatically - no need to thread
these values through every function signature.

Set once per request by the logging middleware (request_id, timing)
and enriched later, as soon as they become known, by the patient
access-gate dependency (hospital_id/department_id/patient_id) and the
admin auth dependency (admin_id). Values default to None until set.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
hospital_id_var: ContextVar[str | None] = ContextVar("hospital_id", default=None)
department_id_var: ContextVar[str | None] = ContextVar("department_id", default=None)
patient_id_var: ContextVar[str | None] = ContextVar("patient_id", default=None)
admin_id_var: ContextVar[str | None] = ContextVar("admin_id", default=None)


def get_log_context() -> dict:
    return {
        "request_id": request_id_var.get(),
        "hospital_id": hospital_id_var.get(),
        "department_id": department_id_var.get(),
        "patient_id": patient_id_var.get(),
        "admin_id": admin_id_var.get(),
    }


def reset_request_scoped_context() -> None:
    """
    Called at the start of every request (by the middleware) so
    values from a previous request on the same worker thread never
    leak into the next one.
    """
    hospital_id_var.set(None)
    department_id_var.set(None)
    patient_id_var.set(None)
    admin_id_var.set(None)