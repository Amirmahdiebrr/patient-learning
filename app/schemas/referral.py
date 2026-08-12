"""
app/schemas/referral.py

Pydantic v2 DTOs for referral intake (manual + API) and hospital API
key management. Every clinical field is optional by design.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ReferralSubmitRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    national_id: str | None = None
    phone_number: str | None = None
    insurance_code: str | None = None

    chief_complaint: str | None = None
    primary_diagnosis: str | None = None
    secondary_diagnoses: str | None = None
    procedures_performed: str | None = None
    medical_history: str | None = None
    allergies: str | None = None
    vital_signs_summary: str | None = None
    discharge_medications: str | None = None
    care_instructions: str | None = None
    follow_up_recommendations: str | None = None
    additional_notes: str | None = None

    attending_physician_name: str | None = None
    referring_department_name: str | None = None
    admission_date: date | None = None
    discharge_date: date | None = None

    attachment_file_url: str | None = Field(default=None, max_length=1024)


class ReferralResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_access_profile_id: uuid.UUID | None
    source: str
    status: str

    first_name: str | None
    last_name: str | None
    national_id: str | None
    phone_number: str | None
    insurance_code: str | None

    chief_complaint: str | None
    primary_diagnosis: str | None
    secondary_diagnoses: str | None
    procedures_performed: str | None
    medical_history: str | None
    allergies: str | None
    vital_signs_summary: str | None
    discharge_medications: str | None
    care_instructions: str | None
    follow_up_recommendations: str | None
    additional_notes: str | None

    attending_physician_name: str | None
    referring_department_name: str | None
    admission_date: date | None
    discharge_date: date | None
    attachment_file_url: str | None

    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralListResponse(BaseModel):
    total: int
    rows: list[ReferralResponse]


class HospitalApiKeyCreateRequest(BaseModel):
    hospital_id: uuid.UUID
    label: str | None = Field(default=None, max_length=255)


class HospitalApiKeyResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    label: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HospitalApiKeyCreatedResponse(HospitalApiKeyResponse):
    api_key: str  # shown only once, at creation time