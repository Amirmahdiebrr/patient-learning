"""
app/api/v1/admin_lesson_draft.py

Admin-only endpoint that asks the AI provider to draft educational
lesson content for a content_manager/admin to review and edit before
publishing. See app/services/lesson_draft_prompt.py for the prompt
itself - this is a DRAFT ONLY, never shown to a patient directly; a
human must approve it via the normal POST /admin/lessons endpoint
(app/api/v1/admin_content.py::create_lesson).

Takes department_type_id (not a real hospital Department id) because
the content builder in panel.html works at the department_type level
(shared library), not against one hospital's actual Department rows.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, RoleCode, JourneyStage, StandardDepartmentType
from app.api.deps_admin import ScopeCheck
from app.services.lesson_draft_prompt import build_lesson_draft_prompt
from app.infrastructure.external.ai_provider import ask_ai, AIProviderError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin_lesson_draft"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))


class LessonDraftGenerateRequest(BaseModel):
    journey_stage_id: uuid.UUID
    department_type_id: uuid.UUID | None = None
    has_surgery: bool | None = None
    topic_hint: str | None = Field(default=None, max_length=255)


class LessonDraftGenerateResponse(BaseModel):
    draft_text: str


@router.post("/lessons/generate-draft", response_model=LessonDraftGenerateResponse)
async def generate_lesson_draft(
    payload: LessonDraftGenerateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    stage = db.query(JourneyStage).filter(JourneyStage.id == payload.journey_stage_id).first()
    if not stage:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرحله‌ی سفر بیمار پیدا نشد.")

    department_name = "عمومی (همه‌ی بخش‌ها)"
    if payload.department_type_id:
        dept_type = db.query(StandardDepartmentType).filter(
            StandardDepartmentType.id == payload.department_type_id
        ).first()
        if not dept_type:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع بخش استاندارد پیدا نشد.")
        department_name = dept_type.name

    prompt = build_lesson_draft_prompt(
        department_name=department_name,
        stage_name=stage.name,
        has_surgery=payload.has_surgery,
        topic_hint=payload.topic_hint,
    )

    try:
        draft_text = await ask_ai(prompt)
    except AIProviderError as exc:
        logger.error(f"[LessonDraft] AIProviderError: {exc}")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    return LessonDraftGenerateResponse(draft_text=draft_text)