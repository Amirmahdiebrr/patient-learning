"""
app/schemas/content_admin.py

Pydantic v2 DTOs for admin content management, including hospital
override lessons and quiz questions (lesson-scoped OR stage-scoped,
with flexible option counts and optional images).
"""

import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


def slugify(value: str) -> str:
    return "-".join(value.strip().lower().split())


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


class JourneyStageResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    display_order: int

    model_config = {"from_attributes": True}


class EducationSectionCreateRequest(BaseModel):
    journey_stage_id: uuid.UUID
    department_type_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    display_order: int = 0


class EducationSectionUpdateRequest(BaseModel):
    journey_stage_id: uuid.UUID
    department_type_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)


class EducationSectionResponse(BaseModel):
    id: uuid.UUID
    journey_stage_id: uuid.UUID
    department_type_id: uuid.UUID | None
    department_type_name: str | None
    treatment_id: uuid.UUID | None
    title: str
    display_order: int
    is_active: bool
    lesson_count: int = 0

    model_config = {"from_attributes": True}


class LessonCreateRequest(BaseModel):
    section_id: uuid.UUID
    title: str = Field(min_length=2, max_length=255)
    body_richtext: str | None = None
    display_order: int = 0
    is_published: bool = False


class LessonUpdateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body_richtext: str | None = None


class LessonResponse(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    title: str
    body_richtext: str | None
    display_order: int
    is_published: bool
    override_level: str = "global"
    parent_lesson_id: uuid.UUID | None = None
    hospital_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class LessonSearchResultResponse(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    title: str
    body_snippet: str | None
    is_published: bool
    journey_stage_name: str
    department_type_name: str | None

    model_config = {"from_attributes": True}


class HospitalOverrideCreateRequest(BaseModel):
    hospital_id: uuid.UUID
    title: str = Field(min_length=2, max_length=255)
    body_richtext: str | None = None
    is_published: bool = False


class MediaAssetCreateRequest(BaseModel):
    lesson_id: uuid.UUID
    type: str
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


class MediaUploadResponse(BaseModel):
    url: str
    original_filename: str
    size_bytes: int


# ---- Quiz (lesson-scoped OR stage-scoped, flexible options, images) ----

class QuizOptionCreateRequest(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)
    option_image_url: str | None = None
    is_correct: bool = False
    display_order: int = 0


class QuizOptionResponse(BaseModel):
    id: uuid.UUID
    option_text: str
    option_image_url: str | None
    is_correct: bool
    display_order: int

    model_config = {"from_attributes": True}


class QuizQuestionCreateRequest(BaseModel):
    lesson_id: uuid.UUID | None = None
    journey_stage_id: uuid.UUID | None = None
    department_type_id: uuid.UUID | None = None
    question_text: str = Field(min_length=2)
    question_image_url: str | None = None
    display_order: int = 0
    options: list[QuizOptionCreateRequest] = Field(min_length=2, max_length=10)

    @field_validator("options")
    @classmethod
    def validate_exactly_one_correct(cls, value: list[QuizOptionCreateRequest]) -> list[QuizOptionCreateRequest]:
        correct_count = sum(1 for opt in value if opt.is_correct)
        if correct_count != 1:
            raise ValueError("دقیقاً یک گزینه باید is_correct=true باشد.")
        return value

    @model_validator(mode="after")
    def validate_exactly_one_target(self):
        if bool(self.lesson_id) == bool(self.journey_stage_id):
            raise ValueError("باید دقیقاً یکی از lesson_id (سوال درسی) یا journey_stage_id (سوال مرحله‌ای) مشخص شود.")
        if self.department_type_id and not self.journey_stage_id:
            raise ValueError("department_type_id فقط برای سوالات مرحله‌ای معنا دارد.")
        return self


class QuizQuestionResponse(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID | None
    journey_stage_id: uuid.UUID | None
    journey_stage_name: str | None = None
    department_type_id: uuid.UUID | None
    department_type_name: str | None = None
    question_text: str
    question_image_url: str | None
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