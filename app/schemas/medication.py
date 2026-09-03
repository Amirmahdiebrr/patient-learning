"""
app/schemas/medication.py
"""

import uuid

from pydantic import BaseModel, Field


class MedicationCreateRequest(BaseModel):
    department_type_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=255)
    body_richtext: str | None = None
    image_url: str | None = Field(default=None, max_length=1024)
    display_order: int = 0


class MedicationUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    body_richtext: str | None = None
    image_url: str | None = Field(default=None, max_length=1024)
    is_active: bool = True
    display_order: int = 0


class MedicationResponse(BaseModel):
    id: uuid.UUID
    department_type_id: uuid.UUID | None
    department_type_name: str | None = None
    name: str
    slug: str
    body_richtext: str | None
    image_url: str | None
    is_active: bool
    display_order: int

    model_config = {"from_attributes": True}