# app/services/content_admin/procedure_classifier_service.py
"""
app/services/content_admin/procedure_classifier_service.py

Classifies each raw imported procedure name into a
StandardDepartmentType. Resolution order:
  1. Deterministic name match: if the admin supplied a department_name
     (or, failing that, the procedure name itself) that matches a
     StandardDepartmentType.name closely enough, use it directly - no
     AI call needed, no chance of hallucination.
  2. AI fallback: any procedure whose department couldn't be matched
     by name is sent to the AI provider in a single batched prompt,
     which guesses department_type_code purely from the procedure
     name. A guess outside the valid code set is discarded.
  3. Anything still unresolved is returned with department_type_code
     = None and an error message; the admin panel forces a manual
     pick before commit.

This mirrors the stage/department matching approach used for lessons
in lesson_classifier_service.py, simplified to a single target field.
"""

import json
import re

from sqlalchemy.orm import Session

from app.infrastructure.db.models import StandardDepartmentType
from app.infrastructure.external.ai_provider import ask_ai, AIProviderError

CLASSIFY_SYSTEM_PROMPT = """
تو دستیار دسته‌بندی «عمل‌های جراحی / پروسیجرهای پزشکی» پلتفرم بیمارستانی
CuraLink هستی.

وظیفه‌ی تو این است که برای هر نام عملی که داده می‌شود، تشخیص بدهی این
عمل معمولاً در کدام «نوع بخش بیمارستانی» انجام می‌شود.

انواع بخش مجاز (department_type_code):
{department_options}

فقط و فقط یک آرایه‌ی JSON خام برگردان (بدون Markdown، بدون توضیح
اضافه)، دقیقاً به همان ترتیب که نام‌ها داده شده‌اند، با این ساختار
برای هر عمل:
[
  {{"department_type_code": "..." یا null}}
]
اگر برای عملی نتوانستی با اطمینان بخش مناسب را تشخیص بدهی، مقدار
department_type_code را null بگذار - هرگز حدس بی‌پایه نزن.

نام‌های عمل:
{names_block}
"""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _match_department_by_name(name: str | None, department_types: list[StandardDepartmentType]) -> str | None:
    if not name:
        return None
    normalized = _normalize(name)
    for dept in department_types:
        dept_name_normalized = _normalize(dept.name)
        if (
            normalized == dept_name_normalized
            or normalized in dept_name_normalized
            or dept_name_normalized in normalized
        ):
            return dept.code
    return None


def _extract_json_array(raw_text: str) -> list:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)

    return json.loads(cleaned)


async def classify_procedures(db: Session, items: list[dict]) -> list[dict]:
    """
    items: [{"name": str, "department_name": str|None}, ...]
    Returns one classification dict per input item, same order:
    {"department_type_code": str|None, "matched_by_name": bool, "error": str|None}
    """
    if not items:
        return []

    department_types = (
        db.query(StandardDepartmentType)
        .filter(StandardDepartmentType.is_active.is_(True))
        .order_by(StandardDepartmentType.macro_category, StandardDepartmentType.display_order)
        .all()
    )
    valid_dept_codes = {d.code for d in department_types}

    name_matched: list[str | None] = [
        _match_department_by_name(item.get("department_name") or item.get("name"), department_types)
        for item in items
    ]

    needs_ai_indices = [i for i, code in enumerate(name_matched) if code is None]
    ai_results: dict[int, dict] = {}

    if needs_ai_indices:
        department_options = "\n".join(f"- {d.code}: {d.name}" for d in department_types)
        names_block = "\n".join(
            f"{pos + 1}. {items[i]['name']}" for pos, i in enumerate(needs_ai_indices)
        )

        prompt = CLASSIFY_SYSTEM_PROMPT.format(
            department_options=department_options,
            names_block=names_block,
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
            entry = parsed[pos] if pos < len(parsed) and isinstance(parsed[pos], dict) else {}
            ai_results[original_index] = {"raw": entry}

    results = []
    for i, item in enumerate(items):
        dept_code = name_matched[i]
        matched_by_name = dept_code is not None
        error = None

        if dept_code is None:
            entry = ai_results.get(i, {})
            if "error" in entry:
                error = entry["error"]
            else:
                candidate = entry.get("raw", {}).get("department_type_code")
                dept_code = candidate if candidate in valid_dept_codes else None
                if dept_code is None:
                    error = "نوع بخش تشخیص داده نشد - لطفاً دستی انتخاب کنید."

        results.append({
            "department_type_code": dept_code,
            "matched_by_name": matched_by_name,
            "error": error,
        })

    return results