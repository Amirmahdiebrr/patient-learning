# app/services/content_admin/lesson_classifier_service.py
"""
app/services/content_admin/lesson_classifier_service.py

Uses the AI provider to guess WHERE each patient-written lesson
belongs (journey stage + standard department type + a short section
label). Procedure resolution is NEVER guessed by AI - it is only
assigned via a direct, deterministic name match against the
Procedure catalog of the already-resolved department, exactly as the
instructions require (no hallucinated procedure assignment).

If the admin explicitly supplies stage_name/department_name text for
a lesson, that name is matched directly against JourneyStage.name /
StandardDepartmentType.name BEFORE calling the AI. Only lessons
missing a confident name match for a field fall back to AI
classification for that field.

Name matching itself (whitespace/invisible-character normalization,
and correct exact-before-substring/longest-substring resolution for
catalog names that are substrings of each other, e.g. "ICU" inside
"NICU"/"PICU") lives in app/services/content_admin/name_matching.py -
see that module's docstring for the specific bugs this fixes.
"""

import json
import re

from sqlalchemy.orm import Session

from app.infrastructure.db.models import JourneyStage, StandardDepartmentType, Procedure
from app.infrastructure.external.ai_provider import ask_ai, AIProviderError
from app.services.content_admin.name_matching import find_best_name_match

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


def _match_stage_by_name(name: str | None, stages: list[JourneyStage]) -> str | None:
    if not name:
        return None
    matched = find_best_name_match(name, stages, name_getter=lambda s: s.name)
    return matched.code.value if matched else None


def _match_department_by_name(name: str | None, department_types: list[StandardDepartmentType]) -> str | None:
    if not name:
        return None
    matched = find_best_name_match(name, department_types, name_getter=lambda d: d.name)
    return matched.code if matched else None


def _match_procedure_by_name(db: Session, department_type_id, name: str | None) -> str | None:
    """
    Direct, deterministic name match only - never AI-assisted. A
    procedure that isn't matched simply stays unassigned (the lesson
    remains department-general); it is never guessed from lesson body.
    """
    if not name or not department_type_id:
        return None
    procedures = (
        db.query(Procedure)
        .filter(Procedure.department_type_id == department_type_id, Procedure.is_active.is_(True))
        .all()
    )
    matched = find_best_name_match(name, procedures, name_getter=lambda p: p.name)
    return matched.slug if matched else None


async def classify_lessons(db: Session, lessons: list[dict]) -> list[dict]:
    """
    lessons: [{"title": str, "body": str|None, "stage_name": str|None,
               "department_name": str|None, "procedure_name": str|None}, ...]
    Returns one classification dict per input lesson, same order:
    {"journey_stage_code": str|None, "department_type_code": str|None,
     "procedure_code": str|None, "section_title": str, "error": str|None,
     "matched_by_name": bool}
    """
    if not lessons:
        return []

    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    department_types = db.query(StandardDepartmentType).filter(
        StandardDepartmentType.is_active.is_(True)
    ).order_by(
        StandardDepartmentType.macro_category, StandardDepartmentType.display_order
    ).all()

    valid_stage_codes = {s.code.value for s in stages}
    valid_dept_codes = {d.code for d in department_types}
    dept_by_code = {d.code: d for d in department_types}

    name_matched_stage: list[str | None] = [_match_stage_by_name(l.get("stage_name"), stages) for l in lessons]
    name_matched_dept: list[str | None] = [_match_department_by_name(l.get("department_name"), department_types) for l in lessons]

    needs_ai_indices = [i for i, lesson in enumerate(lessons) if name_matched_stage[i] is None]

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

        procedure_code = None
        if dept_code and dept_code in dept_by_code:
            procedure_code = _match_procedure_by_name(
                db, dept_by_code[dept_code].id, lesson.get("procedure_name"),
            )

        section_title = (lesson.get("department_name") or lesson.get("stage_name") or lesson["title"]).strip()[:255]
        if not matched_by_name:
            ai_entry = ai_results.get(i, {})
            raw_item = ai_entry.get("raw", {})
            section_title = (raw_item.get("section_title") or lesson["title"]).strip()[:255]

        results.append({
            "journey_stage_code": stage_code,
            "department_type_code": dept_code,
            "procedure_code": procedure_code,
            "section_title": section_title,
            "error": error,
            "matched_by_name": matched_by_name,
        })

    return results