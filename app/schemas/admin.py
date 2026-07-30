"""
app/schemas/admin.py

Pydantic v2 DTOs for admin CRUD operations (hospitals, departments,
QR access points).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


def slugify(value: str) -> str:
    return "-".join(value.strip().lower().split())


class HospitalCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class HospitalResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool

    model_config = {"from_attributes": True}


class DepartmentCreateRequest(BaseModel):
    hospital_id: uuid.UUID
    name: str = Field(min_length=2, max_length=255)


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    slug: str
    is_active: bool

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