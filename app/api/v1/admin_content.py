"""
app/api/v1/admin_content.py

Admin CRUD for the SHARED educational content library: Disease ->
Treatment, and JourneyStage -> EducationSection -> Lesson ->
MediaAsset / QuizQuestion / ContentTargetingRule. EducationSection is
keyed by (journey_stage, department_type) - not by hospital - so
building it once makes it available to every hospital that has a
Department of that type. Only super_admin and content_manager may
create/edit it.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Disease, Treatment, JourneyStage, EducationSection, Lesson,
    RoleCode, AdminUser, MediaAsset, MediaType, QuizQuestion, QuizOption,
    ContentTargetingRule, Hospital, Department, StandardDepartmentType,
)
from app.schemas.content_admin import (
    DiseaseCreateRequest, DiseaseResponse,
    TreatmentCreateRequest, TreatmentResponse,
    JourneyStageResponse,
    EducationSectionCreateRequest, EducationSectionResponse,
    LessonCreateRequest, LessonResponse,
    MediaAssetCreateRequest, MediaAssetResponse,
    QuizQuestionCreateRequest, QuizQuestionResponse,
    ContentTargetingRuleCreateRequest, ContentTargetingRuleResponse,
    slugify,
)
from app.api.deps_admin import ScopeCheck

router = APIRouter(prefix="/admin", tags=["admin_content"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))


def _to_section_response(section: EducationSection) -> EducationSectionResponse:
    return EducationSectionResponse(
        id=section.id,
        journey_stage_id=section.journey_stage_id,
        department_type_id=section.department_type_id,
        department_type_name=section.department_type.name if section.department_type else None,
        treatment_id=section.treatment_id,
        title=section.title,
        display_order=section.display_order,
        is_active=section.is_active,
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
    disease = Disease(
        name=payload.name,
        slug=slugify(payload.name),
        description=payload.description,
    )
    db.add(disease)
    db.commit()
    db.refresh(disease)
    return disease


@router.get("/diseases", response_model=list[DiseaseResponse])
async def list_diseases(db: Session = Depends(get_db)):
    return db.query(Disease).filter(Disease.is_active.is_(True)).order_by(Disease.name).all()


# ==========================
# Treatment
# ==========================

@router.post("/treatments", response_model=TreatmentResponse)
async def create_treatment(
    payload: TreatmentCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    disease = db.query(Disease).filter(Disease.id == payload.disease_id).first()
    if not disease:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بیماری پیدا نشد.")

    treatment = Treatment(
        disease_id=disease.id,
        name=payload.name,
        slug=slugify(payload.name),
        description=payload.description,
    )
    db.add(treatment)
    db.commit()
    db.refresh(treatment)
    return treatment


@router.get("/diseases/{disease_id}/treatments", response_model=list[TreatmentResponse])
async def list_treatments(disease_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(Treatment)
        .filter(Treatment.disease_id == disease_id, Treatment.is_active.is_(True))
        .order_by(Treatment.name)
        .all()
    )


# ==========================
# JourneyStage (read-only - fixed lookup, seeded once)
# ==========================

@router.get("/journey-stages", response_model=list[JourneyStageResponse])
async def list_journey_stages(db: Session = Depends(get_db)):
    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    return [
        JourneyStageResponse(id=s.id, code=s.code.value, name=s.name, display_order=s.display_order)
        for s in stages
    ]


# ==========================
# EducationSection (shared library: journey_stage + department_type)
#
# department_type_id query param semantics:
#   - omitted entirely           -> no department-type filter (all)
#   - "general"                  -> only sections with department_type_id IS NULL
#   - a real UUID                -> only sections with that exact department_type_id
# ==========================

@router.post("/education-sections", response_model=EducationSectionResponse)
async def create_education_section(
    payload: EducationSectionCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    stage = db.query(JourneyStage).filter(JourneyStage.id == payload.journey_stage_id).first()
    if not stage:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرحله‌ی سفر بیمار پیدا نشد.")

    if payload.department_type_id:
        dept_type = db.query(StandardDepartmentType).filter(
            StandardDepartmentType.id == payload.department_type_id
        ).first()
        if not dept_type:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع بخش استاندارد پیدا نشد.")

    if payload.treatment_id:
        treatment = db.query(Treatment).filter(Treatment.id == payload.treatment_id).first()
        if not treatment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "درمان/عمل پیدا نشد.")

    section = EducationSection(
        journey_stage_id=payload.journey_stage_id,
        department_type_id=payload.department_type_id,
        treatment_id=payload.treatment_id,
        title=payload.title,
        display_order=payload.display_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return _to_section_response(section)


@router.get("/education-sections", response_model=list[EducationSectionResponse])
async def list_education_sections(
    journey_stage_id: uuid.UUID | None = None,
    department_type_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(EducationSection).filter(EducationSection.is_active.is_(True))

    if journey_stage_id:
        query = query.filter(EducationSection.journey_stage_id == journey_stage_id)

    if department_type_id == "general":
        query = query.filter(EducationSection.department_type_id.is_(None))
    elif department_type_id:
        try:
            parsed_type_id = uuid.UUID(department_type_id)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شناسه‌ی نوع بخش نامعتبر است.")
        query = query.filter(EducationSection.department_type_id == parsed_type_id)

    sections = query.order_by(EducationSection.display_order).all()
    return [_to_section_response(s) for s in sections]


# ==========================
# Lesson
# ==========================

@router.post("/lessons", response_model=LessonResponse)
async def create_lesson(
    payload: LessonCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    section = db.query(EducationSection).filter(EducationSection.id == payload.section_id).first()
    if not section:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش آموزشی پیدا نشد.")

    lesson = Lesson(
        section_id=payload.section_id,
        title=payload.title,
        body_richtext=payload.body_richtext,
        display_order=payload.display_order,
        is_published=payload.is_published,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


@router.get("/lessons", response_model=list[LessonResponse])
async def list_lessons(section_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(Lesson)
        .filter(Lesson.section_id == section_id)
        .order_by(Lesson.display_order)
        .all()
    )


@router.post("/lessons/{lesson_id}/publish", response_model=LessonResponse)
async def publish_lesson(
    lesson_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    lesson.is_published = True
    db.commit()
    db.refresh(lesson)
    return lesson


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonResponse)
async def unpublish_lesson(
    lesson_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    lesson.is_published = False
    db.commit()
    db.refresh(lesson)
    return lesson


# ==========================
# MediaAsset
# ==========================

@router.post("/media-assets", response_model=MediaAssetResponse)
async def create_media_asset(
    payload: MediaAssetCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == payload.lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    media = MediaAsset(
        lesson_id=payload.lesson_id,
        type=MediaType(payload.type),
        file_url=payload.file_url,
        thumbnail_url=payload.thumbnail_url,
        duration_seconds=payload.duration_seconds,
        display_order=payload.display_order,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


@router.get("/lessons/{lesson_id}/media-assets", response_model=list[MediaAssetResponse])
async def list_media_assets(lesson_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(MediaAsset)
        .filter(MediaAsset.lesson_id == lesson_id)
        .order_by(MediaAsset.display_order)
        .all()
    )


@router.delete("/media-assets/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_asset(
    media_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    media = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not media:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل پیدا نشد.")
    db.delete(media)
    db.commit()


# ==========================
# Quiz (question + options together)
# ==========================

@router.post("/quiz-questions", response_model=QuizQuestionResponse)
async def create_quiz_question(
    payload: QuizQuestionCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == payload.lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    question = QuizQuestion(
        lesson_id=payload.lesson_id,
        question_text=payload.question_text,
        display_order=payload.display_order,
    )
    db.add(question)
    db.flush()

    for i, opt in enumerate(payload.options):
        db.add(QuizOption(
            question_id=question.id,
            option_text=opt.option_text,
            is_correct=opt.is_correct,
            display_order=opt.display_order or i,
        ))

    db.commit()
    db.refresh(question)
    return question


@router.get("/lessons/{lesson_id}/quiz-questions", response_model=list[QuizQuestionResponse])
async def list_quiz_questions(lesson_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(QuizQuestion)
        .filter(QuizQuestion.lesson_id == lesson_id)
        .order_by(QuizQuestion.display_order)
        .all()
    )


@router.delete("/quiz-questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz_question(
    question_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سوال پیدا نشد.")
    db.delete(question)
    db.commit()


# ==========================
# ContentTargetingRule (optional fine-grained override)
# ==========================

@router.post("/content-targeting-rules", response_model=ContentTargetingRuleResponse)
async def create_content_targeting_rule(
    payload: ContentTargetingRuleCreateRequest,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == payload.lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    if payload.hospital_id:
        hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
        if not hospital:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "بیمارستان پیدا نشد.")

    if payload.department_id:
        dept_query = db.query(Department).filter(Department.id == payload.department_id)
        if payload.hospital_id:
            dept_query = dept_query.filter(Department.hospital_id == payload.hospital_id)
        department = dept_query.first()
        if not department:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "بخش پیدا نشد یا به این بیمارستان تعلق ندارد.")

    rule = ContentTargetingRule(
        lesson_id=payload.lesson_id,
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
        disease_id=payload.disease_id,
        treatment_id=payload.treatment_id,
        min_age=payload.min_age,
        max_age=payload.max_age,
        gender=payload.gender,
        priority=payload.priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/lessons/{lesson_id}/targeting-rules", response_model=list[ContentTargetingRuleResponse])
async def list_content_targeting_rules(lesson_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(ContentTargetingRule)
        .filter(ContentTargetingRule.lesson_id == lesson_id)
        .order_by(ContentTargetingRule.priority.desc())
        .all()
    )


@router.delete("/content-targeting-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_targeting_rule(
    rule_id: uuid.UUID,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    rule = db.query(ContentTargetingRule).filter(ContentTargetingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "این قانون پیدا نشد.")
    db.delete(rule)
    db.commit()