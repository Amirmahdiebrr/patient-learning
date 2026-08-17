"""
app/schemas/content_bulk_import.py

Pydantic v2 DTOs for the "smart import" flow: the admin uploads a
file of already-written lessons (title + body only - no stage/
department metadata), the AI classifier suggests where each one
belongs, the admin reviews/edits those suggestions in the panel, and
only then are sections/lessons actually created (see
admin_smart_import.py + lesson_classifier_service.py +
smart_import_commit_service.py).
"""

from pydantic import BaseModel, Field


class RawLessonImportItem(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body: str | None = None


class RawLessonImportPayload(BaseModel):
    lessons: list[RawLessonImportItem] = Field(min_length=1)


class ClassifiedLessonItem(BaseModel):
    title: str
    body: str | None
    journey_stage_code: str | None
    department_type_code: str | None
    section_title: str
    error: str | None = None


class ClassifyResponse(BaseModel):
    stage_options: list[dict]            # [{code, name}]
    department_type_options: list[dict]  # [{code, name}]
    items: list[ClassifiedLessonItem]


class SmartImportCommitItem(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body: str | None = None
    journey_stage_code: str
    department_type_code: str | None = None  # null/"general" = عمومی
    section_title: str = Field(min_length=1, max_length=255)
    is_published: bool = True


class SmartImportCommitPayload(BaseModel):
    items: list[SmartImportCommitItem] = Field(min_length=1)


class SmartImportCommitSummaryResponse(BaseModel):
    sections_created: int
    sections_reused: int
    lessons_created: int
    lessons_updated: int
    errors: list[str]