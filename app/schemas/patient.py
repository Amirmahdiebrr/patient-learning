"""
app/schemas/patient.py

Pydantic v2 DTOs for the patient-facing onboarding + journey flow.
"""

import uuid

from pydantic import BaseModel, Field, field_validator


class OnboardingSubmitRequest(BaseModel):
    disease_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    has_surgery: bool | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"male", "female", "other"}
        if value not in allowed:
            raise ValueError("gender must be one of: male, female, other")
        return value


class OnboardingOptionsResponse(BaseModel):
    """
    Options shown to the patient on the onboarding form, scoped to the
    department resolved from their QR access point.
    """
    diseases: list[dict]
    treatments_by_disease: dict[str, list[dict]]


class PatientAssistantAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[dict] = Field(default_factory=list)