"""
app/services/patient_assistant_service.py

Builds the context-aware prompt for the patient AI assistant. If a
specific lesson is being viewed (focus_lesson), its content is placed
first and flagged as "the lesson the patient is currently reading",
so the assistant answers questions about that lesson accurately
before falling back to the rest of the journey's content.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import PatientJourneyProfile, Lesson
from app.infrastructure.external.ai_provider import ask_ai, AIProviderError
from app.services.content_targeting_service import get_lessons_for_journey
from app.services.patient_assistant_prompt import PATIENT_ASSISTANT_SYSTEM_PROMPT
from app.core.logging_config import get_logger

logger = get_logger(__name__)

MAX_LESSON_CONTEXT_CHARS = 6000
NO_CONTEXT_TEXT = "هیچ محتوای آموزشی اختصاصی برای این مرحله ثبت نشده است."
NO_HISTORY_TEXT = "بدون مکالمه‌ی قبلی."


class PatientAssistantService:

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return NO_HISTORY_TEXT

        lines = []
        for turn in history[-6:]:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            speaker = "بیمار" if role == "user" else "دستیار"
            lines.append(f"{speaker}: {content}")

        return "\n".join(lines) if lines else NO_HISTORY_TEXT

    def _build_lesson_context(
        self,
        db: Session,
        journey: PatientJourneyProfile,
        hospital_id: uuid.UUID,
        department_id: uuid.UUID,
        department_type_id: uuid.UUID | None,
        focus_lesson: Lesson | None,
    ) -> str:
        parts = []

        if focus_lesson and focus_lesson.body_richtext:
            parts.append(
                f"### {focus_lesson.title} (درسی که بیمار در حال حاضر آن را می‌خواند - "
                f"اولویت پاسخ با این محتواست)\n{focus_lesson.body_richtext}"
            )

        lessons = get_lessons_for_journey(
            db, journey,
            hospital_id=hospital_id,
            department_id=department_id,
            department_type_id=department_type_id,
        )

        for lesson in lessons:
            if focus_lesson and lesson.id == focus_lesson.id:
                continue
            if lesson.body_richtext:
                parts.append(f"### {lesson.title}\n{lesson.body_richtext}")

        if not parts:
            return NO_CONTEXT_TEXT

        combined = "\n\n".join(parts)
        return combined[:MAX_LESSON_CONTEXT_CHARS] if combined else NO_CONTEXT_TEXT

    async def ask(
        self,
        db: Session,
        journey: PatientJourneyProfile,
        question: str,
        history: list[dict],
        hospital_id: uuid.UUID,
        department_id: uuid.UUID,
        department_type_id: uuid.UUID | None,
        focus_lesson: Lesson | None = None,
    ) -> str:

        lesson_context = self._build_lesson_context(
            db, journey, hospital_id, department_id, department_type_id, focus_lesson
        )
        history_text = self._format_history(history)

        prompt = PATIENT_ASSISTANT_SYSTEM_PROMPT.format(
            lesson_context=lesson_context,
            history=history_text,
            question=question.strip(),
        )

        try:
            return await ask_ai(prompt)
        except AIProviderError as exc:
            logger.error(f"[PatientAssistant] AIProviderError: {exc}")
            raise