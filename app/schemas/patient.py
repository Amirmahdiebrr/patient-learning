# app/schemas/patient.py
"""
app/schemas/patient.py
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PatientRegistrationSubmitRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    national_id: str = Field(min_length=8, max_length=20)
    phone_number: str = Field(min_length=8, max_length=20)
    insurance_code: str | None = Field(default=None, max_length=100)

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"\d{10}", digits):
            raise ValueError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
        return digits

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"09\d{9}", digits):
            raise ValueError("شماره همراه باید با ۰۹ شروع شود و ۱۱ رقم باشد.")
        return digits


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
    diseases: list[dict]
    treatments_by_disease: dict[str, list[dict]]


class PatientAssistantAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[dict] = Field(default_factory=list)
    lesson_id: uuid.UUID | None = None


class LessonProgressUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"not_started", "in_progress", "completed"}
        if value not in allowed:
            raise ValueError(f"status باید یکی از این مقادیر باشد: {', '.join(allowed)}")
        return value


class QuizAttemptRequest(BaseModel):
    option_id: uuid.UUID


# ==========================
# Self-service patient auth (no QR needed)
# ==========================

class PatientSelfRegisterRequest(BaseModel):
    hospital_id: uuid.UUID
    department_id: uuid.UUID

    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    national_id: str = Field(min_length=8, max_length=20)
    phone_number: str = Field(min_length=8, max_length=20)
    insurance_code: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    disease_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    has_surgery: bool | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"\d{10}", digits):
            raise ValueError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
        return digits

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"09\d{9}", digits):
            raise ValueError("شماره همراه باید با ۰۹ شروع شود و ۱۱ رقم باشد.")
        return digits

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"male", "female", "other"}
        if value not in allowed:
            raise ValueError("gender باید یکی از این مقادیر باشد: male, female, other")
        return value


class PatientLoginRequest(BaseModel):
    national_id: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class PatientSelfAuthResponse(BaseModel):
    redirect_url: str


# ==========================
# Patient profile (view/edit/avatar)
# ==========================

class PatientProfileResponse(BaseModel):
    first_name: str
    last_name: str
    national_id: str
    phone_number: str
    insurance_code: str | None
    avatar_url: str | None
    hospital_name: str | None
    department_name: str | None
    current_stage_name: str | None
    disease_name: str | None
    treatment_name: str | None
    age: int | None
    gender: str | None
    has_surgery: bool | None
    member_since: datetime


class PatientProfileUpdateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    phone_number: str = Field(min_length=8, max_length=20)
    insurance_code: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"09\d{9}", digits):
            raise ValueError("شماره همراه باید با ۰۹ شروع شود و ۱۱ رقم باشد.")
        return digits

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"male", "female", "other"}
        if value not in allowed:
            raise ValueError("gender باید یکی از این مقادیر باشد: male, female, other")
        return value