# app/api/v1/patient_lessons.py
"""
app/api/v1/patient_lessons.py

Patient-facing lesson detail page + progress/favorite/quiz-attempt
endpoints. All state keyed to patient_access_profile_id (anonymous
device profile) - never to any real identity.

A lesson cannot be marked COMPLETED while it still has unanswered
quiz questions of its own - update_progress() enforces this
server-side (not just via a disabled button in the template) so it
can never be bypassed by calling the API directly.

lesson_detail() additionally resolves the previous/next published
lesson within the same EducationSection (ordered by display_order) so
the redesigned lesson page can render prev/next navigation buttons -
this is read-only sequencing info, it does not change how lessons are
resolved/targeted for a patient (see content_targeting_service.py).

Publishes LessonCompleted when progress transitions to "completed",
and QuizCompleted on every quiz attempt submission. After both of
these, try_auto_advance_stage() checks whether the patient's current
journey stage is now fully done (every lesson completed + every
stage-level quiz question attempted) and, if so, automatically moves
them to the next applicable stage - see
patient_journey_state_machine.py for the full rules.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.events import LessonCompleted, QuizCompleted
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import (
    Lesson, ProgressRecord, LessonProgressStatus, FavoriteRecord,
    QuizQuestion, QuizOption, QuizAttempt, PatientJourneyProfile,
)
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.schemas.patient import LessonProgressUpdateRequest, QuizAttemptRequest
from app.core.templates import templates
from app.services.patient_journey_state_machine import try_auto_advance_stage

router = APIRouter(tags=["patient_lessons"])


def _lesson_quiz_fully_answered(db: Session, lesson: Lesson, patient_access_profile_id: uuid.UUID) -> bool:
    question_ids = [q.id for q in lesson.quiz_questions]
    if not question_ids:
        return True

    attempted_count = (
        db.query(QuizAttempt.question_id)
        .filter(
            QuizAttempt.patient_access_profile_id == patient_access_profile_id,
            QuizAttempt.question_id.in_(question_ids),
        )
        .distinct()
        .count()
    )
    return attempted_count >= len(question_ids)


def _sibling_lessons(db: Session, lesson: Lesson) -> tuple[Lesson | None, Lesson | None]:
    """
    Returns (previous, next) PUBLISHED lesson within the same section,
    ordered by display_order (ties broken by created_at) - purely for
    the reading-flow prev/next buttons on the lesson page.
    """
    siblings = (
        db.query(Lesson)
        .filter(Lesson.section_id == lesson.section_id, Lesson.is_published.is_(True))
        .order_by(Lesson.display_order, Lesson.created_at)
        .all()
    )
    try:
        idx = next(i for i, l in enumerate(siblings) if l.id == lesson.id)
    except StopIteration:
        return None, None

    previous_lesson = siblings[idx - 1] if idx > 0 else None
    next_lesson = siblings[idx + 1] if idx < len(siblings) - 1 else None
    return previous_lesson, next_lesson


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

    answered_question_ids = {
        row[0] for row in
        db.query(QuizAttempt.question_id)
        .filter(
            QuizAttempt.patient_access_profile_id == context.patient_profile.id,
            QuizAttempt.question_id.in_([q.id for q in lesson.quiz_questions]),
        )
        .distinct()
        .all()
    }
    quiz_complete = _lesson_quiz_fully_answered(db, lesson, context.patient_profile.id)

    previous_lesson, next_lesson = _sibling_lessons(db, lesson)

    return templates.TemplateResponse(
        request,
        "lesson_detail.html",
        {
            "request": request,
            "lesson": lesson,
            "progress": progress,
            "is_favorite": is_favorite,
            "answered_question_ids": answered_question_ids,
            "quiz_complete": quiz_complete,
            "previous_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "section_title": lesson.section.title,
        },
    )


@router.post("/lessons/{lesson_id}/progress")
async def update_progress(
    lesson_id: uuid.UUID,
    payload: LessonProgressUpdateRequest,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درس پیدا نشد.")

    new_status = LessonProgressStatus(payload.status)

    if new_status == LessonProgressStatus.COMPLETED and not _lesson_quiz_fully_answered(
        db, lesson, context.patient_profile.id
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "قبل از تکمیل این درس باید به تمام سوالات آزمون آن پاسخ دهید.",
        )

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

    was_already_completed = progress.status == LessonProgressStatus.COMPLETED
    progress.status = new_status

    if new_status == LessonProgressStatus.IN_PROGRESS and not progress.started_at:
        progress.started_at = datetime.utcnow()
    if new_status == LessonProgressStatus.COMPLETED:
        progress.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(progress)

    if new_status == LessonProgressStatus.COMPLETED and not was_already_completed:
        event_bus.publish(LessonCompleted(
            patient_access_profile_id=context.patient_profile.id,
            lesson_id=lesson_id,
        ))

        try_auto_advance_stage(
            db, journey,
            patient_access_profile_id=context.patient_profile.id,
            hospital_id=context.hospital_id,
            department_id=context.department_id,
            department_type_id=context.department.department_type_id,
        )

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
    journey: PatientJourneyProfile = Depends(get_active_journey),
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

    event_bus.publish(QuizCompleted(
        patient_access_profile_id=context.patient_profile.id,
        question_id=question_id,
        is_correct=option.is_correct,
    ))

    try_auto_advance_stage(
        db, journey,
        patient_access_profile_id=context.patient_profile.id,
        hospital_id=context.hospital_id,
        department_id=context.department_id,
        department_type_id=context.department.department_type_id,
    )

    correct_option = next((o for o in question.options if o.is_correct), None)

    return JSONResponse({
        "is_correct": option.is_correct,
        "correct_option_id": str(correct_option.id) if correct_option else None,
    })