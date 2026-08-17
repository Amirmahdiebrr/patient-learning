"""
app/services/content_admin/lesson_classifier_service.py

Uses the AI provider to guess WHERE each patient-written lesson
belongs (journey stage + standard department type + a short section
label) based on its title/body - it never rewrites or generates the
lesson content itself, only classifies placement. Admin reviews/edits
the suggestions before anything is actually created (see
admin_smart_import.py).
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


async def classify_lessons(db: Session, lessons: list[dict]) -> list[dict]:
    """
    lessons: [{"title": str, "body": str|None}, ...]
    Returns one classification dict per input lesson, same order:
    {"journey_stage_code": str|None, "department_type_code": str|None,
     "section_title": str, "error": str|None}
    A per-item "error" is set (with a safe fallback) if the AI's
    answer for that index was missing/malformed - the rest of the
    batch is unaffected.
    """
    if not lessons:
        return []

    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    department_types = db.query(StandardDepartmentType).order_by(
        StandardDepartmentType.macro_category, StandardDepartmentType.display_order
    ).all()

    stage_options = "\n".join(f"- {s.code.value}: {s.name}" for s in stages)
    department_options = "\n".join(f"- {d.code}: {d.name}" for d in department_types)

    prompt = CLASSIFY_SYSTEM_PROMPT.format(
        stage_options=stage_options,
        department_options=department_options,
        lessons_block=_build_lessons_block(lessons),
    )

    try:
        raw_response = await ask_ai(prompt)
    except AIProviderError:
        return [
            {"journey_stage_code": None, "department_type_code": None, "section_title": l["title"], "error": "پاسخ هوش مصنوعی دریافت نشد."}
            for l in lessons
        ]

    try:
        parsed = _extract_json_array(raw_response)
    except (json.JSONDecodeError, ValueError):
        return [
            {"journey_stage_code": None, "department_type_code": None, "section_title": l["title"], "error": "پاسخ هوش مصنوعی قابل تجزیه نبود."}
            for l in lessons
        ]

    valid_stage_codes = {s.code.value for s in stages}
    valid_dept_codes = {d.code for d in department_types}

    results = []
    for i, lesson in enumerate(lessons):
        item = parsed[i] if i < len(parsed) and isinstance(parsed[i], dict) else {}

        stage_code = item.get("journey_stage_code")
        if stage_code not in valid_stage_codes:
            stage_code = None
            error = "مرحله تشخیص داده نشد - لطفاً دستی انتخاب کنید."
        else:
            error = None

        dept_code = item.get("department_type_code")
        if dept_code not in valid_dept_codes:
            dept_code = None

        section_title = (item.get("section_title") or lesson["title"]).strip()[:255]

        results.append({
            "journey_stage_code": stage_code,
            "department_type_code": dept_code,
            "section_title": section_title,
            "error": error,
        })

    return results