"""
app/services/content_admin/lesson_classifier_service.py

Uses the AI provider to guess WHERE each patient-written lesson
belongs (journey stage + standard department type + a short section
label) based on its title/body - it never rewrites or generates the
lesson content itself, only classifies placement.

If the admin explicitly supplies stage_name/department_name text for
a lesson in the import file, that name is matched directly against
JourneyStage.name / StandardDepartmentType.name (case-insensitive,
substring match) BEFORE calling the AI - a confident name match skips
AI guessing entirely for that field, so admin-supplied names always
take priority over AI inference. Only lessons missing a confident
name match for a field fall back to AI classification for that field.
"""

import json
import re

from sqlalchemy.orm import Session

from app.infrastructure.db.models import JourneyStage, StandardDepartmentType
from app.infrastructure.external.ai_provider import ask_ai, AIProviderError

MAX_BODY_CHARS_FOR_CLASSIFICATION = 500

CLASSIFY_SYSTEM_PROMPT = """
تو دستیار دسته‌بندی محتوای آموزشی پلتفرم بیمارستانی CuraLink هستی.

وظیفه‌ی تو این است که برای هر «درس» (که یک پرستار/ادمین از قبل نوشته)
تشخیص بدهی این درس مربوط به کدام «مرحله‌ی سفر بیمار» و کدام «نوع بخش
بیمارستانی» است، و یک برچسب کوتاه فارسی (section_title) برای گروه‌بندی
آن پیشنهاد بدهی. تو هرگز متن درس را تغییر نمی‌دهی یا تولید نمی‌کنی -
فقط محل درست آن را تشخیص می‌دهی.

مراحل مجاز (journey_stage_code):
{stage_options}

انواع بخش مجاز (department_type_code) - اگر درس عمومی است و به بخش
خاصی مربوط نیست، مقدار null بگذار:
{department_options}

فقط و فقط یک آرایه‌ی JSON خام برگردان (بدون Markdown، بدون توضیح
اضافه)، دقیقاً به همین ترتیب که دروس داده شده‌اند، با این ساختار
برای هر درس:
[
  {{"journey_stage_code": "...", "department_type_code": "..." یا null, "section_title": "یک برچسب کوتاه فارسی"}}
]

دروس:
{lessons_block}
"""


def _build_lessons_block(lessons: list[dict]) -> str:
    parts = []
    for i, lesson in enumerate(lessons):
        body_snippet = (lesson.get("body") or "")[:MAX_BODY_CHARS_FOR_CLASSIFICATION]
        parts.append(f"{i + 1}. عنوان: {lesson['title']}\nخلاصه‌ی متن: {body_snippet}")
    return "\n\n".join(parts)


def _extract_json_array(raw_text: str) -> list:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)

    return json.loads(cleaned)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _match_stage_by_name(name: str | None, stages: list[JourneyStage]) -> str | None:
    if not name:
        return None
    normalized = _normalize(name)
    for stage in stages:
        stage_name_normalized = _normalize(stage.name)
        if normalized == stage_name_normalized or normalized in stage_name_normalized or stage_name_normalized in normalized:
            return stage.code.value
    return None


def _match_department_by_name(name: str | None, department_types: list[StandardDepartmentType]) -> str | None:
    if not name:
        return None
    normalized = _normalize(name)
    for dept in department_types:
        dept_name_normalized = _normalize(dept.name)
        if normalized == dept_name_normalized or normalized in dept_name_normalized or dept_name_normalized in normalized:
            return dept.code
    return None


async def classify_lessons(db: Session, lessons: list[dict]) -> list[dict]:
    """
    lessons: [{"title": str, "body": str|None, "stage_name": str|None,
               "department_name": str|None}, ...]
    Returns one classification dict per input lesson, same order:
    {"journey_stage_code": str|None, "department_type_code": str|None,
     "section_title": str, "error": str|None, "matched_by_name": bool}

    For each lesson, stage_name/department_name (if given) are matched
    directly against DB names first. Only lessons still missing a
    stage_code or department_code after name-matching are sent to the
    AI, and only for the field(s) still missing.
    """
    if not lessons:
        return []

    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    department_types = db.query(StandardDepartmentType).order_by(
        StandardDepartmentType.macro_category, StandardDepartmentType.display_order
    ).all()

    valid_stage_codes = {s.code.value for s in stages}
    valid_dept_codes = {d.code for d in department_types}

    # Pre-resolve everything possible via direct name matching.
    name_matched_stage: list[str | None] = [_match_stage_by_name(l.get("stage_name"), stages) for l in lessons]
    name_matched_dept: list[str | None] = [_match_department_by_name(l.get("department_name"), department_types) for l in lessons]

    needs_ai_indices = [
        i for i, lesson in enumerate(lessons)
        if name_matched_stage[i] is None
    ]

    ai_results: dict[int, dict] = {}

    if needs_ai_indices:
        ai_lessons = [lessons[i] for i in needs_ai_indices]

        stage_options = "\n".join(f"- {s.code.value}: {s.name}" for s in stages)
        department_options = "\n".join(f"- {d.code}: {d.name}" for d in department_types)

        prompt = CLASSIFY_SYSTEM_PROMPT.format(
            stage_options=stage_options,
            department_options=department_options,
            lessons_block=_build_lessons_block(ai_lessons),
        )

        try:
            raw_response = await ask_ai(prompt)
            parsed = _extract_json_array(raw_response)
        except AIProviderError:
            parsed = None
        except (json.JSONDecodeError, ValueError):
            parsed = None

        for pos, original_index in enumerate(needs_ai_indices):
            if parsed is None:
                ai_results[original_index] = {"error": "پاسخ هوش مصنوعی دریافت یا تجزیه نشد."}
                continue
            item = parsed[pos] if pos < len(parsed) and isinstance(parsed[pos], dict) else {}
            ai_results[original_index] = {"raw": item}

    results = []
    for i, lesson in enumerate(lessons):
        stage_code = name_matched_stage[i]
        dept_code = name_matched_dept[i]
        error = None
        matched_by_name = stage_code is not None

        if stage_code is None:
            ai_entry = ai_results.get(i, {})
            if "error" in ai_entry:
                error = ai_entry["error"]
            else:
                raw_item = ai_entry.get("raw", {})
                candidate_stage = raw_item.get("journey_stage_code")
                stage_code = candidate_stage if candidate_stage in valid_stage_codes else None
                if stage_code is None:
                    error = "مرحله تشخیص داده نشد - لطفاً دستی انتخاب کنید."

                if dept_code is None:
                    candidate_dept = raw_item.get("department_type_code")
                    dept_code = candidate_dept if candidate_dept in valid_dept_codes else None

        section_title = (lesson.get("department_name") or lesson.get("stage_name") or lesson["title"]).strip()[:255]
        if not matched_by_name:
            ai_entry = ai_results.get(i, {})
            raw_item = ai_entry.get("raw", {})
            section_title = (raw_item.get("section_title") or lesson["title"]).strip()[:255]

        results.append({
            "journey_stage_code": stage_code,
            "department_type_code": dept_code,
            "section_title": section_title,
            "error": error,
            "matched_by_name": matched_by_name,
        })

    return results