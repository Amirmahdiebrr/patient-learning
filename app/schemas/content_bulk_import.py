# app/schemas/content_bulk_import.py
"""
app/schemas/content_bulk_import.py
"""

from pydantic import BaseModel, Field, field_validator


class RawQuizOptionImportItem(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)
    option_image_url: str | None = None
    is_correct: bool = False


class RawQuizQuestionImportItem(BaseModel):
    question_text: str = Field(min_length=2)
    question_image_url: str | None = None
    options: list[RawQuizOptionImportItem] = Field(min_length=2, max_length=10)

    @field_validator("options")
    @classmethod
    def validate_exactly_one_correct(cls, value: list[RawQuizOptionImportItem]) -> list[RawQuizOptionImportItem]:
        correct_count = sum(1 for opt in value if opt.is_correct)
        if correct_count != 1:
            raise ValueError("دقیقاً یک گزینه باید is_correct=true باشد.")
        return value


class RawLessonImportItem(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body: str | None = None
    stage_name: str | None = Field(default=None, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    procedure_name: str | None = Field(default=None, max_length=255)
    quiz_questions: list[RawQuizQuestionImportItem] = Field(default_factory=list)


class RawLessonImportPayload(BaseModel):
    lessons: list[RawLessonImportItem] = Field(min_length=1)


class ClassifiedLessonItem(BaseModel):
    title: str
    body: str | None
    journey_stage_code: str | None
    department_type_code: str | None
    procedure_code: str | None = None
    section_title: str
    quiz_questions: list[RawQuizQuestionImportItem] = Field(default_factory=list)
    error: str | None = None
    matched_by_name: bool = False


class ClassifyResponse(BaseModel):
    stage_options: list[dict]
    department_type_options: list[dict]
    items: list[ClassifiedLessonItem]


class SmartImportCommitItem(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body: str | None = None
    journey_stage_code: str
    department_type_code: str | None = None
    procedure_code: str | None = None
    section_title: str = Field(min_length=1, max_length=255)
    is_published: bool = True
    quiz_questions: list[RawQuizQuestionImportItem] = Field(default_factory=list)


class SmartImportCommitPayload(BaseModel):
    items: list[SmartImportCommitItem] = Field(min_length=1)


class SmartImportCommitSummaryResponse(BaseModel):
    sections_created: int
    sections_reused: int
    lessons_created: int
    lessons_updated: int
    quiz_questions_created: int
    errors: list[str]