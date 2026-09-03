"""
app/services/content_admin/content_export_service.py

خروجی گرفتن از کل محتوای آموزشی (دروس + آزمون‌ها) برای تحلیل توسط
هوش مصنوعی - به‌صورت یک فایل کلی یا چند فایل تفکیک‌شده بر اساس
مرحله‌ی سفر بیمار یا نوع بخش، در فرمت Markdown یا JSON.
"""

import html
import io
import json
import re
import zipfile
from datetime import datetime

import bleach
from sqlalchemy.orm import Session, joinedload

from app.infrastructure.db.models import (
    Lesson, EducationSection, JourneyStage, StandardDepartmentType,
    QuizQuestion, LessonOverrideLevel,
)


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = bleach.clean(text, tags=[], strip=True)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_filename(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    text = re.sub(r"\s+", "-", text)
    return text[:80] or "file"


def _quiz_question_dict(q: QuizQuestion) -> dict:
    return {
        "question_text": q.question_text,
        "options": [
            {"text": o.option_text, "is_correct": o.is_correct}
            for o in sorted(q.options, key=lambda o: o.display_order)
        ],
    }


def collect_export_data(db: Session, include_drafts: bool = True) -> dict:
    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    dept_types = db.query(StandardDepartmentType).order_by(
        StandardDepartmentType.macro_category, StandardDepartmentType.display_order
    ).all()
    dept_by_id = {d.id: d for d in dept_types}

    stages_out = []

    for stage in stages:
        departments_map: dict = {}

        sections = (
            db.query(EducationSection)
            .options(
                joinedload(EducationSection.lessons).joinedload(Lesson.quiz_questions),
                joinedload(EducationSection.procedure),
            )
            .filter(EducationSection.journey_stage_id == stage.id)
            .order_by(EducationSection.department_type_id, EducationSection.display_order)
            .all()
        )

        for section in sections:
            lessons = [
                l for l in section.lessons
                if l.override_level == LessonOverrideLevel.GLOBAL and (include_drafts or l.is_published)
            ]
            if not lessons:
                continue

            dept_key = section.department_type_id
            dept_entry = departments_map.setdefault(dept_key, {
                "department_type_id": str(dept_key) if dept_key else None,
                "department_type_name": dept_by_id[dept_key].name if dept_key else "عمومی (همه‌ی بخش‌ها)",
                "sections": [],
                "stage_level_quiz_questions": [],
            })

            section_dict = {
                "title": section.title,
                "procedure_name": section.procedure.name if section.procedure else None,
                "lessons": [
                    {
                        "title": lesson.title,
                        "is_published": lesson.is_published,
                        "body_text": html_to_text(lesson.body_richtext),
                        "quiz_questions": [
                            _quiz_question_dict(q)
                            for q in sorted(lesson.quiz_questions, key=lambda q: q.display_order)
                        ],
                    }
                    for lesson in sorted(lessons, key=lambda l: l.display_order)
                ],
            }
            dept_entry["sections"].append(section_dict)

        stage_quizzes = (
            db.query(QuizQuestion)
            .options(joinedload(QuizQuestion.options))
            .filter(QuizQuestion.journey_stage_id == stage.id, QuizQuestion.lesson_id.is_(None))
            .order_by(QuizQuestion.department_type_id, QuizQuestion.display_order)
            .all()
        )
        for q in stage_quizzes:
            dept_key = q.department_type_id
            dept_entry = departments_map.setdefault(dept_key, {
                "department_type_id": str(dept_key) if dept_key else None,
                "department_type_name": dept_by_id[dept_key].name if dept_key else "عمومی (همه‌ی بخش‌ها)",
                "sections": [],
                "stage_level_quiz_questions": [],
            })
            dept_entry["stage_level_quiz_questions"].append(_quiz_question_dict(q))

        if not departments_map:
            continue

        stages_out.append({
            "stage_code": stage.code.value,
            "stage_name": stage.name,
            "departments": list(departments_map.values()),
        })

    return {"generated_at": datetime.utcnow().isoformat(), "stages": stages_out}


def _render_quiz_block(questions: list[dict], title: str) -> list[str]:
    lines = [f"### {title}", ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q['question_text']}")
        for opt in q["options"]:
            mark = "✓" if opt["is_correct"] else "-"
            lines.append(f"   - [{mark}] {opt['text']}")
    lines.append("")
    return lines


def render_lesson_markdown(lesson: dict) -> str:
    status = "منتشرشده" if lesson["is_published"] else "پیش‌نویس"
    lines = [f"#### درس: {lesson['title']} ({status})"]
    if lesson["body_text"]:
        lines += ["", lesson["body_text"]]
    if lesson["quiz_questions"]:
        lines += [""] + _render_quiz_block(lesson["quiz_questions"], "سوالات آزمون")
    lines.append("")
    return "\n".join(lines)


def render_department_markdown(dept: dict, with_header: bool = True) -> str:
    lines = []
    if with_header:
        lines.append(f"## بخش: {dept['department_type_name']}")
        lines.append("")
    for section in dept["sections"]:
        proc = f" (عمل: {section['procedure_name']})" if section["procedure_name"] else ""
        lines.append(f"### برچسب: {section['title']}{proc}")
        lines.append("")
        for lesson in section["lessons"]:
            lines.append(render_lesson_markdown(lesson))
    if dept["stage_level_quiz_questions"]:
        lines += _render_quiz_block(dept["stage_level_quiz_questions"], "آزمون عمومی این بخش/مرحله")
    return "\n".join(lines)


def render_stage_markdown(stage: dict) -> str:
    lines = [f"# مرحله: {stage['stage_name']}", ""]
    for dept in stage["departments"]:
        lines.append(render_department_markdown(dept))
    return "\n".join(lines)


def render_full_markdown(data: dict) -> str:
    lines = ["# آموزش‌های CuraLink", f"_تاریخ خروجی: {data['generated_at']}_", ""]
    for stage in data["stages"]:
        lines.append(render_stage_markdown(stage))
    return "\n".join(lines)


def build_markdown_files(data: dict, split_by: str) -> dict[str, str]:
    if split_by == "none":
        return {"curalink-content-export.md": render_full_markdown(data)}

    if split_by == "stage":
        files = {}
        for i, stage in enumerate(data["stages"], 1):
            fname = f"{i:02d}-{safe_filename(stage['stage_name'])}.md"
            files[fname] = render_stage_markdown(stage)
        return files

    if split_by == "department":
        dept_map: dict = {}
        for stage in data["stages"]:
            for dept in stage["departments"]:
                dept_map.setdefault(dept["department_type_name"], []).append((stage["stage_name"], dept))

        files = {}
        for i, (dept_name, entries) in enumerate(sorted(dept_map.items()), 1):
            lines = [f"# بخش: {dept_name}", ""]
            for stage_name, dept in entries:
                lines.append(f"## مرحله: {stage_name}")
                lines.append("")
                lines.append(render_department_markdown(dept, with_header=False))
            fname = f"{i:02d}-{safe_filename(dept_name)}.md"
            files[fname] = "\n".join(lines)
        return files

    raise ValueError("invalid split_by")


def build_json_files(data: dict, split_by: str) -> dict[str, str]:
    if split_by == "none":
        return {"curalink-content-export.json": json.dumps(data, ensure_ascii=False, indent=2)}

    if split_by == "stage":
        files = {}
        for i, stage in enumerate(data["stages"], 1):
            fname = f"{i:02d}-{safe_filename(stage['stage_name'])}.json"
            files[fname] = json.dumps(stage, ensure_ascii=False, indent=2)
        return files

    if split_by == "department":
        dept_map: dict = {}
        for stage in data["stages"]:
            for dept in stage["departments"]:
                entry = dept_map.setdefault(dept["department_type_name"], {
                    "department_type_name": dept["department_type_name"], "stages": [],
                })
                entry["stages"].append({"stage_name": stage["stage_name"], **dept})

        files = {}
        for i, (name, payload) in enumerate(sorted(dept_map.items()), 1):
            fname = f"{i:02d}-{safe_filename(name)}.json"
            files[fname] = json.dumps(payload, ensure_ascii=False, indent=2)
        return files

    raise ValueError("invalid split_by")


def build_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            zf.writestr(fname, content)
    return buf.getvalue()