"""
app/api/v1/patient_lessons.py

Patient-facing lesson detail page + progress/favorite/quiz-attempt
endpoints. All state keyed to patient_access_profile_id (anonymous
device profile) - never to any real identity.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Lesson, ProgressRecord, LessonProgressStatus, FavoriteRecord,
    QuizQuestion, QuizOption, QuizAttempt, PatientJourneyProfile,
)
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.schemas.patient import LessonProgressUpdateRequest, QuizAttemptRequest
from app.core.templates import templates

router = APIRouter(tags=["patient_lessons"])


@router.get("/lessons/{lesson_id}")
async def lesson_detail(
    request: Request,
    lesson_id: uuid.UUID,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    lesson = (
        db.query(Lesson)
        .filter(Lesson.id == lesson_id, Lesson.is_published.is_(True))
        .first()
    )
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    progress = (
        db.query(ProgressRecord)
        .filter(
            ProgressRecord.patient_access_profile_id == context.patient_profile.id,
            ProgressRecord.lesson_id == lesson.id,
        )
        .first()
    )

    if not progress:
        progress = ProgressRecord(
            patient_access_profile_id=context.patient_profile.id,
            lesson_id=lesson.id,
            status=LessonProgressStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    elif progress.status == LessonProgressStatus.NOT_STARTED:
        progress.status = LessonProgressStatus.IN_PROGRESS
        progress.started_at = datetime.utcnow()
        db.commit()
        db.refresh(progress)

    is_favorite = (
        db.query(FavoriteRecord)
        .filter(
            FavoriteRecord.patient_access_profile_id == context.patient_profile.id,
            FavoriteRecord.lesson_id == lesson.id,
        )
        .first()
        is not None
    )

    return templates.TemplateResponse(
        request,
        "lesson_detail.html",
        {
            "request": request,
            "lesson": lesson,
            "progress": progress,
            "is_favorite": is_favorite,
        },
    )


@router.post("/lessons/{lesson_id}/progress")
async def update_progress(
    lesson_id: uuid.UUID,
    payload: LessonProgressUpdateRequest,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    progress = (
        db.query(ProgressRecord)
        .filter(
            ProgressRecord.patient_access_profile_id == context.patient_profile.id,
            ProgressRecord.lesson_id == lesson_id,
        )
        .first()
    )

    if not progress:
        progress = ProgressRecord(
            patient_access_profile_id=context.patient_profile.id,
            lesson_id=lesson_id,
        )
        db.add(progress)

    new_status = LessonProgressStatus(payload.status)
    progress.status = new_status

    if new_status == LessonProgressStatus.IN_PROGRESS and not progress.started_at:
        progress.started_at = datetime.utcnow()
    if new_status == LessonProgressStatus.COMPLETED:
        progress.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(progress)

    return JSONResponse({"status": progress.status.value})


@router.post("/lessons/{lesson_id}/favorite")
async def add_favorite(
    lesson_id: uuid.UUID,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    existing = (
        db.query(FavoriteRecord)
        .filter(
            FavoriteRecord.patient_access_profile_id == context.patient_profile.id,
            FavoriteRecord.lesson_id == lesson_id,
        )
        .first()
    )
    if not existing:
        db.add(FavoriteRecord(
            patient_access_profile_id=context.patient_profile.id,
            lesson_id=lesson_id,
        ))
        db.commit()

    return JSONResponse({"is_favorite": True})


@router.delete("/lessons/{lesson_id}/favorite")
async def remove_favorite(
    lesson_id: uuid.UUID,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(FavoriteRecord)
        .filter(
            FavoriteRecord.patient_access_profile_id == context.patient_profile.id,
            FavoriteRecord.lesson_id == lesson_id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()

    return JSONResponse({"is_favorite": False})


@router.post("/quiz-questions/{question_id}/attempt")
async def submit_quiz_attempt(
    question_id: uuid.UUID,
    payload: QuizAttemptRequest,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سوال پیدا نشد.")

    option = (
        db.query(QuizOption)
        .filter(QuizOption.id == payload.option_id, QuizOption.question_id == question_id)
        .first()
    )
    if not option:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گزینه پیدا نشد.")

    attempt = QuizAttempt(
        patient_access_profile_id=context.patient_profile.id,
        question_id=question_id,
        selected_option_id=option.id,
        is_correct=option.is_correct,
    )
    db.add(attempt)
    db.commit()

    correct_option = next((o for o in question.options if o.is_correct), None)

    return JSONResponse({
        "is_correct": option.is_correct,
        "correct_option_id": str(correct_option.id) if correct_option else None,
    })