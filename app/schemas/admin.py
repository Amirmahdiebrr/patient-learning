# app/schemas/admin.py
"""
app/schemas/admin.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr, field_validator


def slugify(value: str) -> str:
    return "-".join(value.strip().lower().split())


class HospitalCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class HospitalUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class HospitalResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool

    model_config = {"from_attributes": True}


class DepartmentCreateRequest(BaseModel):
    hospital_id: uuid.UUID
    department_type_id: uuid.UUID
    name: str | None = Field(default=None, max_length=255)


class DepartmentUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    department_type_id: uuid.UUID | None = None


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    department_type_id: uuid.UUID | None
    department_type_name: str | None

    model_config = {"from_attributes": True}


class StandardDepartmentTypeResponse(BaseModel):
    id: uuid.UUID
    macro_category: str
    code: str
    name: str
    display_order: int

    model_config = {"from_attributes": True}


class QRAccessPointCreateRequest(BaseModel):
    hospital_id: uuid.UUID
    department_id: uuid.UUID
    label: str | None = None


class QRAccessPointResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    department_id: uuid.UUID
    label: str | None
    status: str
    entry_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Admin users + roles ----

class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleAssignmentCreateRequest(BaseModel):
    admin_user_id: uuid.UUID
    role_code: str
    hospital_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, value: str) -> str:
        allowed = {"super_admin", "hospital_admin", "department_admin", "doctor", "content_manager"}
        if value not in allowed:
            raise ValueError(f"role_code باید یکی از این مقادیر باشد: {', '.join(allowed)}")
        return value


class RoleAssignmentResponse(BaseModel):
    id: uuid.UUID
    admin_user_id: uuid.UUID
    role_code: str
    hospital_id: uuid.UUID | None
    department_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Hospital self-service signup ----

class HospitalSignupRequest(BaseModel):
    hospital_name: str = Field(min_length=2, max_length=255)
    hospital_address: str | None = Field(default=None, max_length=500)
    hospital_phone: str | None = Field(default=None, max_length=20)

    admin_full_name: str = Field(min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)
    responsible_phone: str | None = Field(default=None, max_length=20)
    responsible_national_id: str | None = Field(default=None, max_length=20)


# ---- Pending hospital approval (super_admin review) ----

class PendingHospitalResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    phone_number: str | None
    responsible_phone: str | None
    responsible_national_id: str | None
    responsible_full_name: str | None
    responsible_email: str | None
    created_at: datetime