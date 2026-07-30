"""
app/schemas/content_admin.py

Pydantic v2 DTOs for admin content management (Disease, Treatment,
EducationSection, Lesson). This content is global - not scoped to a
specific hospital - since it's shared/reusable across hospitals.
"""

import uuid

from pydantic import BaseModel, Field


def slugify(value: str) -> str:
    return "-".join(value.strip().lower().split())


# ---- Disease ----

class DiseaseCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None


class DiseaseResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---- Treatment ----

class TreatmentCreateRequest(BaseModel):
    disease_id: uuid.UUID
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None


class TreatmentResponse(BaseModel):
    id: uuid.UUID
    disease_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---- JourneyStage (read-only, fixed lookup) ----

class JourneyStageResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    display_order: int

    model_config = {"from_attributes": True}


# ---- EducationSection ----

class EducationSectionCreateRequest(BaseModel):
    journey_stage_id: uuid.UUID
    treatment_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    display_order: int = 0


class EducationSectionResponse(BaseModel):
    id: uuid.UUID
    journey_stage_id: uuid.UUID
    treatment_id: uuid.UUID | None
    title: str
    display_order: int
    is_active: bool

    model_config = {"from_attributes": True}


# ---- Lesson ----

class LessonCreateRequest(BaseModel):
    section_id: uuid.UUID
    title: str = Field(min_length=2, max_length=255)
    body_richtext: str | None = None
    display_order: int = 0
    is_published: bool = False


class LessonResponse(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    title: str
    body_richtext: str | None
    display_order: int
    is_published: bool

    model_config = {"from_attributes": True}