"""
app/schemas/nurse.py
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class NurseRegisterRequest(BaseModel):
    hospital_id: uuid.UUID
    department_id: uuid.UUID | None = None
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    national_id: str = Field(min_length=8, max_length=20)
    nursing_license_number: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"\d{10}", digits):
            raise ValueError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
        return digits

    @field_validator("nursing_license_number")
    @classmethod
    def validate_license_number(cls, value: str) -> str:
        return value.strip()


class NurseRegisterResponse(BaseModel):
    message: str = "درخواست ثبت‌نام شما ثبت شد و در انتظار تایید ادمین بیمارستان است."


class NurseLoginRequest(BaseModel):
    national_id: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        digits = value.strip()
        if not re.fullmatch(r"\d{10}", digits):
            raise ValueError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
        return digits


class NurseAuthResponse(BaseModel):
    full_name: str
    email: str


class NurseMeResponse(BaseModel):
    full_name: str
    email: str
    hospital_name: str
    department_name: str | None


# ---- Admin-facing nurse approval ----

class NurseAdminRowResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    national_id: str
    nursing_license_number: str
    hospital_name: str
    department_name: str | None
    is_active: bool
    created_at: datetime
    approved_at: datetime | None

    model_config = {"from_attributes": True}


class NurseAdminListResponse(BaseModel):
    total: int
    rows: list[NurseAdminRowResponse]