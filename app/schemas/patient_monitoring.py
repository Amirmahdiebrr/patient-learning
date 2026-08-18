"""
app/schemas/patient_monitoring.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class PatientMonitoringRowResponse(BaseModel):
    patient_access_profile_id: uuid.UUID
    first_name: str
    last_name: str
    hospital_name: str
    department_name: str
    current_stage_code: str
    current_stage_name: str
    current_stage_lessons_total: int
    current_stage_lessons_completed: int
    current_stage_percent: float
    total_lessons_completed: int
    quiz_total: int
    quiz_correct: int
    quiz_success_percent: float
    onboarding_completed: bool
    days_since_registration: int
    last_activity_at: datetime | None
    days_inactive: int | None
    needs_attention: bool


class PatientMonitoringResponse(BaseModel):
    total: int
    rows: list[PatientMonitoringRowResponse]