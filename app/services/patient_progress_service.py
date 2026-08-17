"""
app/services/patient_progress_service.py

Builds the data behind the patient-facing "مسیر درمان من" page:
per-stage lesson-completion counts/percentages, an overall progress
percentage, and the patient's full quiz attempt history (correct/
incorrect per question, across both lesson-level and stage-level
quizzes).
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import PatientJourneyProfile, QuizAttempt, QuizQuestion, QuizOption
from app.services.content_targeting_service import get_journey_timeline


def get_journey_progress(
    db: Session,
    journey: PatientJourneyProfile,
    patient_access_profile_id: uuid.UUID,
    hospital_id: uuid.UUID,
    department_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
) -> dict:
    timeline = get_journey_timeline(
        db, journey, patient_access_profile_id,
        hospital_id, department_id, department_type_id,
    )

    stages = []
    total_lessons = 0
    total_completed = 0

    for stage in timeline:
        stage_total = len(stage["lessons"])
        stage_completed = sum(1 for item in stage["lessons"] if item["is_completed"])
        percent = round((stage_completed / stage_total) * 100) if stage_total else 0

        total_lessons += stage_total
        total_completed += stage_completed

        stages.append({
            "stage_name": stage["stage_name"],
            "is_current": stage["is_current"],
            "is_completed": stage["is_completed"],
            "total_lessons": stage_total,
            "completed_lessons": stage_completed,
            "percent": percent,
        })

    overall_percent = round((total_completed / total_lessons) * 100) if total_lessons else 0

    return {
        "stages": stages,
        "total_lessons": total_lessons,
        "completed_lessons": total_completed,
        "overall_percent": overall_percent,
    }


def get_quiz_attempt_history(db: Session, patient_access_profile_id: uuid.UUID, limit: int = 100) -> list[dict]:
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.patient_access_profile_id == patient_access_profile_id)
        .order_by(QuizAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )
    if not attempts:
        return []

    question_ids = {a.question_id for a in attempts}
    questions = {q.id: q for q in db.query(QuizQuestion).filter(QuizQuestion.id.in_(question_ids)).all()}

    option_ids = {a.selected_option_id for a in attempts}
    options = {o.id: o for o in db.query(QuizOption).filter(QuizOption.id.in_(option_ids)).all()}

    correct_options_by_question = {}
    if question_ids:
        for opt in db.query(QuizOption).filter(
            QuizOption.question_id.in_(question_ids), QuizOption.is_correct.is_(True)
        ).all():
            correct_options_by_question[opt.question_id] = opt

    results = []
    for a in attempts:
        question = questions.get(a.question_id)
        selected_option = options.get(a.selected_option_id)
        correct_option = correct_options_by_question.get(a.question_id)

        results.append({
            "question_text": question.question_text if question else "سوال حذف‌شده",
            "is_correct": a.is_correct,
            "selected_option_text": selected_option.option_text if selected_option else "—",
            "correct_option_text": correct_option.option_text if correct_option else None,
            "attempted_at": a.attempted_at,
        })

    return results