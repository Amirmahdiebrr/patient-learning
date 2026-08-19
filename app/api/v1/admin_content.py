# app/api/v1/admin_content.py
"""
app/api/v1/admin_content.py

Thin HTTP layer for the shared educational content library. All
business logic lives in app/services/content_admin/* - this file
only: validates the caller's scope, calls the right service function,
converts service-layer exceptions into HTTPException, and publishes
AdminContentAction audit events.

Hospital-specific writes additionally call ensure_hospital_access
before touching the service layer.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import AdminContentAction
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import RoleCode, AdminUser, JourneyStage
from app.schemas.content_admin import (
    DiseaseCreateRequest, DiseaseResponse,
    TreatmentCreateRequest, TreatmentResponse,
    JourneyStageResponse,
    ProcedureCreateRequest, ProcedureUpdateRequest, ProcedureResponse,
    EducationSectionCreateRequest, EducationSectionUpdateRequest, EducationSectionResponse,
    LessonCreateRequest, LessonUpdateRequest, LessonResponse, LessonSearchResultResponse,
    HospitalOverrideCreateRequest,
    MediaAssetCreateRequest, MediaAssetResponse,
    QuizQuestionCreateRequest, QuizQuestionResponse,
    ContentTargetingRuleCreateRequest, ContentTargetingRuleResponse,
)
from app.api.deps_admin import ScopeCheck
from app.api.deps_common import client_ip
from app.infrastructure.db.repositories.hospital_scoped_repository import ensure_hospital_access
from app.services.content_admin.errors import ContentNotFoundError, ContentConflictError, ContentValidationError
from app.services.content_admin import (
    disease_treatment_service,
    section_service,
    lesson_service,
    media_asset_service,
    quiz_service,
    targeting_rule_service,
    procedure_service,
)

router = APIRouter(prefix="/admin", tags=["admin_content"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))


def _raise_for(exc: Exception):
    if isinstance(exc, ContentNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, ContentConflictError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, ContentValidationError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    raise exc


def _parse_department_type_id(raw: str | None) -> tuple[uuid.UUID | None, bool]:
    if raw == "general":
        return None, True
    if raw:
        try:
            return uuid.UUID(raw), False
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شناسه‌ی نوع بخش نامعتبر است.")
    return None, False


def _to_section_response(section) -> EducationSectionResponse:
    return EducationSectionResponse(
        id=section.id,
        journey_stage_id=section.journey_stage_id,
        department_type_id=section.department_type_id,
        department_type_name=section.department_type.name if section.department_type else None,
        procedure_id=section.procedure_id,
        procedure_name=section.procedure.name if section.procedure else None,
        treatment_id=section.treatment_id,
        title=section.title,
        display_order=section.display_order,
        is_active=section.is_active,
        lesson_count=len(section.lessons),
    )


def _to_procedure_response(procedure) -> ProcedureResponse:
    return ProcedureResponse(
        id=procedure.id,
        department_type_id=procedure.department_type_id,
        name=procedure.name,
        slug=procedure.slug,
        is_active=procedure.is_active,
        display_order=procedure.display_order,
    )


def _to_quiz_response(question) -> QuizQuestionResponse:
    return QuizQuestionResponse(
        id=question.id,
        lesson_id=question.lesson_id,
        journey_stage_id=question.journey_stage_id,
        journey_stage_name=question.journey_stage.name if question.journey_stage else None,
        department_type_id=question.department_type_id,
        department_type_name=question.department_type.name if question.department_type else None,
        procedure_id=question.procedure_id,
        procedure_name=question.procedure.name if question.procedure else None,
        question_text=question.question_text,
        question_image_url=question.question_image_url,
        display_order=question.display_order,
        options=question.options,
    )


# ==========================
# Disease
# ==========================

@router.post("/diseases", response_model=DiseaseResponse)
async def create_disease(
    payload: DiseaseCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    return disease_treatment_service.create_disease(db, payload.name, payload.description)


@router.get("/diseases", response_model=list[DiseaseResponse])
async def list_diseases(db: Session = Depends(get_db)):
    return disease_treatment_service.list_active_diseases(db)


# ==========================
# Treatment
# ==========================

@router.post("/treatments", response_model=TreatmentResponse)
async def create_treatment(
    payload: TreatmentCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        return disease_treatment_service.create_treatment(db, payload.disease_id, payload.name, payload.description)
    except (ContentNotFoundError, ContentConflictError, ContentValidationError) as exc:
        _raise_for(exc)


@router.get("/diseases/{disease_id}/treatments", response_model=list[TreatmentResponse])
async def list_treatments(disease_id: uuid.UUID, db: Session = Depends(get_db)):
    return disease_treatment_service.list_active_treatments(db, disease_id)


# ==========================
# JourneyStage
# ==========================

@router.get("/journey-stages", response_model=list[JourneyStageResponse])
async def list_journey_stages(db: Session = Depends(get_db)):
    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    return [
        JourneyStageResponse(id=s.id, code=s.code.value, name=s.name, display_order=s.display_order)
        for s in stages
    ]


# ==========================
# Procedure
# ==========================

@router.post("/procedures", response_model=ProcedureResponse)
async def create_procedure(
    payload: ProcedureCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        procedure = procedure_service.create_procedure(
            db, payload.department_type_id, payload.name, payload.display_order,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_procedure_response(procedure)


@router.get("/procedures", response_model=list[ProcedureResponse])
async def list_procedures(
    department_type_id: uuid.UUID,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    procedures = procedure_service.list_procedures(db, department_type_id, include_inactive)
    return [_to_procedure_response(p) for p in procedures]


@router.patch("/procedures/{procedure_id}", response_model=ProcedureResponse)
async def update_procedure(
    procedure_id: uuid.UUID,
    payload: ProcedureUpdateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        procedure = procedure_service.update_procedure(
            db, procedure_id, payload.name, payload.is_active, payload.display_order,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_procedure_response(procedure)


@router.post("/procedures/{procedure_id}/deactivate", response_model=ProcedureResponse)
async def deactivate_procedure(
    procedure_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        procedure = procedure_service.set_procedure_active(db, procedure_id, is_active=False)
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_procedure_response(procedure)


@router.post("/procedures/{procedure_id}/reactivate", response_model=ProcedureResponse)
async def reactivate_procedure(
    procedure_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        procedure = procedure_service.set_procedure_active(db, procedure_id, is_active=True)
    except ContentNotFoundError as exc:
        _raise_for(exc)
    return _to_procedure_response(procedure)


# ==========================
# EducationSection
# ==========================

@router.post("/education-sections", response_model=EducationSectionResponse)
async def create_education_section(
    payload: EducationSectionCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        section = section_service.create_section(
            db, payload.journey_stage_id, payload.department_type_id,
            payload.treatment_id, payload.title, payload.display_order,
            procedure_id=payload.procedure_id,
        )
    except (ContentNotFoundError, ContentConflictError, ContentValidationError) as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="create", object_type="education_section", object_id=section.id,
        before=None, after=section_service.section_snapshot(section), ip_address=client_ip(request),
    ))

    return _to_section_response(section)


@router.get("/education-sections", response_model=list[EducationSectionResponse])
async def list_education_sections(
    journey_stage_id: uuid.UUID | None = None,
    department_type_id: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    parsed_id, is_general = _parse_department_type_id(department_type_id)
    sections = section_service.list_sections(db, journey_stage_id, parsed_id, is_general, include_inactive)
    return [_to_section_response(s) for s in sections]


@router.patch("/education-sections/{section_id}", response_model=EducationSectionResponse)
async def update_education_section(
    section_id: uuid.UUID,
    payload: EducationSectionUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        section, before = section_service.update_section(
            db, section_id, payload.journey_stage_id, payload.department_type_id,
            payload.treatment_id, payload.title, procedure_id=payload.procedure_id,
        )
    except (ContentNotFoundError, ContentConflictError, ContentValidationError) as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="update", object_type="education_section", object_id=section.id,
        before=before, after=section_service.section_snapshot(section), ip_address=client_ip(request),
    ))

    return _to_section_response(section)


@router.post("/education-sections/{section_id}/deactivate", response_model=EducationSectionResponse)
async def deactivate_education_section(
    section_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        section, before = section_service.set_section_active(db, section_id, is_active=False)
    except ContentNotFoundError as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="deactivate", object_type="education_section", object_id=section.id,
        before=before, after=section_service.section_snapshot(section), ip_address=client_ip(request),
    ))

    return _to_section_response(section)


@router.post("/education-sections/{section_id}/reactivate", response_model=EducationSectionResponse)
async def reactivate_education_section(
    section_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        section, before = section_service.set_section_active(db, section_id, is_active=True)
    except ContentNotFoundError as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="reactivate", object_type="education_section", object_id=section.id,
        before=before, after=section_service.section_snapshot(section), ip_address=client_ip(request),
    ))

    return _to_section_response(section)


@router.delete("/education-sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_education_section(
    section_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        section_id_copy, before = section_service.delete_section(db, section_id)
    except (ContentNotFoundError, ContentConflictError) as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="delete", object_type="education_section", object_id=section_id_copy,
        before=before, after=None, ip_address=client_ip(request),
    ))


# ==========================
# Lesson
# ==========================

@router.post("/lessons", response_model=LessonResponse)
async def create_lesson(
    payload: LessonCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        lesson = lesson_service.create_lesson(
            db, payload.section_id, payload.title, payload.body_richtext,
            payload.display_order, payload.is_published,
        )
    except (ContentNotFoundError, ContentConflictError, ContentValidationError) as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="create", object_type="lesson", object_id=lesson.id,
        before=None, after=lesson_service.lesson_snapshot(lesson), ip_address=client_ip(request),
    ))

    return lesson


@router.get("/lessons", response_model=list[LessonResponse])
async def list_lessons(section_id: uuid.UUID, db: Session = Depends(get_db)):
    return lesson_service.list_lessons_for_section(db, section_id)


@router.get("/lessons/search", response_model=list[LessonSearchResultResponse])
async def search_lessons(
    q: str = "",
    limit: int = 30,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        lessons = lesson_service.search_lessons(db, q, limit)
    except ContentValidationError as exc:
        _raise_for(exc)

    results = []
    for lesson in lessons:
        snippet = None
        if lesson.body_richtext:
            snippet = lesson.body_richtext[:160] + ("…" if len(lesson.body_richtext) > 160 else "")

        results.append(LessonSearchResultResponse(
            id=lesson.id, section_id=lesson.section_id, title=lesson.title, body_snippet=snippet,
            is_published=lesson.is_published, journey_stage_name=lesson.section.journey_stage.name,
            department_type_name=lesson.section.department_type.name if lesson.section.department_type else None,
        ))

    return results


@router.patch("/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    lesson_id: uuid.UUID,
    payload: LessonUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        lesson, before = lesson_service.update_lesson(db, lesson_id, payload.title, payload.body_richtext)
    except ContentNotFoundError as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="update", object_type="lesson", object_id=lesson.id,
        before=before, after=lesson_service.lesson_snapshot(lesson), ip_address=client_ip(request),
    ))

    return lesson


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    lesson_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        lesson_id_copy, before = lesson_service.delete_lesson(db, lesson_id)
    except ContentNotFoundError as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="delete", object_type="lesson", object_id=lesson_id_copy,
        before=before, after=None, ip_address=client_ip(request),
    ))


@router.post("/lessons/{lesson_id}/publish", response_model=LessonResponse)
async def publish_lesson(
    lesson_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        lesson, before = lesson_service.set_lesson_published(db, lesson_id, is_published=True)
    except ContentNotFoundError as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="publish", object_type="lesson", object_id=lesson.id,
        before=before, after=lesson_service.lesson_snapshot(lesson), ip_address=client_ip(request),
    ))

    return lesson


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonResponse)
async def unpublish_lesson(
    lesson_id: uuid.UUID,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        lesson, before = lesson_service.set_lesson_published(db, lesson_id, is_published=False)
    except ContentNotFoundError as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="unpublish", object_type="lesson", object_id=lesson.id,
        before=before, after=lesson_service.lesson_snapshot(lesson), ip_address=client_ip(request),
    ))

    return lesson


@router.post("/lessons/{lesson_id}/hospital-override", response_model=LessonResponse)
async def create_hospital_override(
    lesson_id: uuid.UUID,
    payload: HospitalOverrideCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    ensure_hospital_access(admin, db, payload.hospital_id)

    try:
        override_lesson = lesson_service.create_hospital_override(
            db, lesson_id, payload.hospital_id, payload.title, payload.body_richtext, payload.is_published,
        )
    except (ContentNotFoundError, ContentConflictError) as exc:
        _raise_for(exc)

    event_bus.publish(AdminContentAction(
        admin_id=admin.id, action="create", object_type="lesson_hospital_override", object_id=override_lesson.id,
        before=None, after=lesson_service.lesson_snapshot(override_lesson), ip_address=client_ip(request),
    ))

    return override_lesson


@router.get("/lessons/{lesson_id}/hospital-overrides", response_model=list[LessonResponse])
async def list_hospital_overrides(
    lesson_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    return lesson_service.list_hospital_overrides(db, lesson_id)


# ==========================
# MediaAsset
# ==========================

@router.post("/media-assets", response_model=MediaAssetResponse)
async def create_media_asset(
    payload: MediaAssetCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        return media_asset_service.create_media_asset(
            db, payload.lesson_id, payload.type, payload.file_url,
            payload.thumbnail_url, payload.duration_seconds, payload.display_order,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)


@router.get("/lessons/{lesson_id}/media-assets", response_model=list[MediaAssetResponse])
async def list_media_assets(lesson_id: uuid.UUID, db: Session = Depends(get_db)):
    return media_asset_service.list_media_assets(db, lesson_id)


@router.delete("/media-assets/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_asset(
    media_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        media_asset_service.delete_media_asset(db, media_id)
    except ContentNotFoundError as exc:
        _raise_for(exc)


# ==========================
# Quiz (lesson-scoped OR stage-scoped)
# ==========================

@router.post("/quiz-questions", response_model=QuizQuestionResponse)
async def create_quiz_question(
    payload: QuizQuestionCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        question = quiz_service.create_quiz_question(
            db, payload.lesson_id, payload.journey_stage_id, payload.department_type_id,
            payload.question_text, payload.question_image_url, payload.display_order, payload.options,
            procedure_id=payload.procedure_id,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)

    return _to_quiz_response(question)


@router.get("/lessons/{lesson_id}/quiz-questions", response_model=list[QuizQuestionResponse])
async def list_quiz_questions(lesson_id: uuid.UUID, db: Session = Depends(get_db)):
    questions = quiz_service.list_lesson_quiz_questions(db, lesson_id)
    return [_to_quiz_response(q) for q in questions]


@router.get("/stage-quiz-questions", response_model=list[QuizQuestionResponse])
async def list_stage_quiz_questions(
    journey_stage_id: uuid.UUID,
    department_type_id: str | None = None,
    procedure_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    parsed_id, is_general = _parse_department_type_id(department_type_id)
    questions = quiz_service.list_stage_quiz_questions(db, journey_stage_id, parsed_id, is_general, procedure_id)
    return [_to_quiz_response(q) for q in questions]


@router.delete("/quiz-questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz_question(
    question_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        quiz_service.delete_quiz_question(db, question_id)
    except ContentNotFoundError as exc:
        _raise_for(exc)


# ==========================
# ContentTargetingRule (optional fine-grained override)
# ==========================

@router.post("/content-targeting-rules", response_model=ContentTargetingRuleResponse)
async def create_content_targeting_rule(
    payload: ContentTargetingRuleCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    if payload.hospital_id:
        ensure_hospital_access(admin, db, payload.hospital_id)

    try:
        return targeting_rule_service.create_targeting_rule(
            db, payload.lesson_id, payload.hospital_id, payload.department_id,
            payload.disease_id, payload.treatment_id,
            payload.min_age, payload.max_age, payload.gender, payload.priority,
        )
    except ContentNotFoundError as exc:
        _raise_for(exc)


@router.get("/lessons/{lesson_id}/targeting-rules", response_model=list[ContentTargetingRuleResponse])
async def list_content_targeting_rules(lesson_id: uuid.UUID, db: Session = Depends(get_db)):
    return targeting_rule_service.list_targeting_rules(db, lesson_id)


@router.delete("/content-targeting-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_targeting_rule(
    rule_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    try:
        targeting_rule_service.delete_targeting_rule(db, rule_id)
    except ContentNotFoundError as exc:
        _raise_for(exc)