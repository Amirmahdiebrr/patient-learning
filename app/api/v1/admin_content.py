"""
app/api/v1/admin_content.py

Admin CRUD for the educational content tree: Disease -> Treatment,
and JourneyStage -> EducationSection -> Lesson. This content is
global (not hospital-scoped) since it's shared/reusable across every
hospital on the platform - only super_admin and content_manager may
create/edit it.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Disease, Treatment, JourneyStage, EducationSection, Lesson, RoleCode, AdminUser,
)
from app.schemas.content_admin import (
    DiseaseCreateRequest, DiseaseResponse,
    TreatmentCreateRequest, TreatmentResponse,
    JourneyStageResponse,
    EducationSectionCreateRequest, EducationSectionResponse,
    LessonCreateRequest, LessonResponse,
    slugify,
)
from app.api.deps_admin import ScopeCheck

router = APIRouter(prefix="/admin", tags=["admin_content"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))


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
# EducationSection
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

    if payload.treatment_id:
        treatment = db.query(Treatment).filter(Treatment.id == payload.treatment_id).first()
        if not treatment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "درمان/عمل پیدا نشد.")

    section = EducationSection(
        journey_stage_id=payload.journey_stage_id,
        treatment_id=payload.treatment_id,
        title=payload.title,
        display_order=payload.display_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.get("/education-sections", response_model=list[EducationSectionResponse])
async def list_education_sections(
    journey_stage_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(EducationSection).filter(EducationSection.is_active.is_(True))
    if journey_stage_id:
        query = query.filter(EducationSection.journey_stage_id == journey_stage_id)
    return query.order_by(EducationSection.display_order).all()


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