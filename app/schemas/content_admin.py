"""
app/schemas/content_admin.py

Pydantic v2 DTOs for admin content management (Disease, Treatment,
EducationSection, Lesson, MediaAsset, QuizQuestion/QuizOption,
ContentTargetingRule). EducationSection content is a SHARED LIBRARY
keyed by (journey_stage, department_type) - not tied to a specific
hospital. Any hospital whose Department is linked to that
department_type automatically receives the content.
"""

import uuid

from pydantic import BaseModel, Field, field_validator


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
    department_type_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    display_order: int = 0


class EducationSectionResponse(BaseModel):
    id: uuid.UUID
    journey_stage_id: uuid.UUID
    department_type_id: uuid.UUID | None
    department_type_name: str | None
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


# ---- MediaAsset ----

class MediaAssetCreateRequest(BaseModel):
    lesson_id: uuid.UUID
    type: str  # "video" | "image" | "pdf" | "animation"
    file_url: str = Field(min_length=1, max_length=1024)
    thumbnail_url: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    display_order: int = 0

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        allowed = {"video", "image", "pdf", "animation"}
        if value not in allowed:
            raise ValueError(f"type باید یکی از این مقادیر باشد: {', '.join(allowed)}")
        return value


class MediaAssetResponse(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    type: str
    file_url: str
    thumbnail_url: str | None
    duration_seconds: int | None
    display_order: int

    model_config = {"from_attributes": True}


# ---- Quiz ----

class QuizOptionCreateRequest(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False
    display_order: int = 0


class QuizOptionResponse(BaseModel):
    id: uuid.UUID
    option_text: str
    is_correct: bool
    display_order: int

    model_config = {"from_attributes": True}


class QuizQuestionCreateRequest(BaseModel):
    lesson_id: uuid.UUID
    question_text: str = Field(min_length=2)
    display_order: int = 0
    options: list[QuizOptionCreateRequest] = Field(min_length=2, max_length=8)

    @field_validator("options")
    @classmethod
    def validate_exactly_one_correct(cls, value: list[QuizOptionCreateRequest]) -> list[QuizOptionCreateRequest]:
        correct_count = sum(1 for opt in value if opt.is_correct)
        if correct_count != 1:
            raise ValueError("دقیقاً یک گزینه باید is_correct=true باشد.")
        return value


class QuizQuestionResponse(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    question_text: str
    display_order: int
    options: list[QuizOptionResponse]

    model_config = {"from_attributes": True}


# ---- ContentTargetingRule (optional fine-grained override) ----

class ContentTargetingRuleCreateRequest(BaseModel):
    lesson_id: uuid.UUID
    hospital_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    disease_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None
    priority: int = 0

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"male", "female", "other"}
        if value not in allowed:
            raise ValueError("gender must be one of: male, female, other")
        return value


class ContentTargetingRuleResponse(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    hospital_id: uuid.UUID | None
    department_id: uuid.UUID | None
    disease_id: uuid.UUID | None
    treatment_id: uuid.UUID | None
    min_age: int | None
    max_age: int | None
    gender: str | None
    priority: int

    model_config = {"from_attributes": True}