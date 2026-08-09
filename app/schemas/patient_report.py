"""
app/schemas/patient_report.py

Pydantic v2 DTOs for the admin-facing patient registration report -
lets hospital/department staff see who registered, their contact
info for follow-ups, and their current journey stage. Read-only,
admin-auth-gated only.
"""

import uuid
from datetime import datetime


from pydantic import BaseModel


class PatientReportRowResponse(BaseModel):
    patient_access_profile_id: uuid.UUID
    first_name: str
    last_name: str
    national_id: str
    phone_number: str
    insurance_code: str | None
    hospital_name: str
    department_name: str
    disease_name: str | None
    treatment_name: str | None
    has_surgery: bool | None
    age: int | None
    gender: str | None
    current_stage_code: str
    current_stage_name: str
    onboarding_completed: bool
    registered_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class PatientReportResponse(BaseModel):
    total: int
    rows: list[PatientReportRowResponse]