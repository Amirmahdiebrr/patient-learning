"""
app/api/v1/admin_smart_import.py
"""

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, RoleCode, JourneyStage, StandardDepartmentType
from app.api.deps_admin import ScopeCheck
from app.schemas.content_bulk_import import (
    RawLessonImportPayload, ClassifyResponse, ClassifiedLessonItem,
    SmartImportCommitPayload, SmartImportCommitSummaryResponse,
)
from app.services.content_admin.lesson_classifier_service import classify_lessons
from app.services.content_admin.smart_import_commit_service import run_smart_import_commit

router = APIRouter(prefix="/admin", tags=["admin_smart_import"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))

SAMPLE_TEMPLATE = {
    "lessons": [
        {
            "title": "در بدو ورود چه اتفاقی می‌افتد؟",
            "body": "متن کامل درسی که خودت نوشته‌ای اینجا قرار می‌گیرد...",
            "stage_name": "پذیرش در بخش",
            "department_name": "ارتوپدی",
            "quiz_questions": [
                {
                    "question_text": "بعد از ورود به بخش، اول باید چه کاری انجام دهید؟",
                    "question_image_url": None,
                    "options": [
                        {"option_text": "به پرستار مراجعه کنید", "option_image_url": None, "is_correct": True},
                        {"option_text": "مستقیم به تخت خود بروید", "option_image_url": None, "is_correct": False}
                    ]
                }
            ]
        },
        {
            "title": "آماده‌سازی قبل از سزارین",
            "body": "متن کامل این درس...",
            "stage_name": None,
            "department_name": None,
            "quiz_questions": []
        }
    ],
    "_help": "عنوان و متن هر درس را بنویس. اگر stage_name/department_name را دقیق بنویسی (مثلاً 'پذیرش در بخش' یا 'ارتوپدی')، سیستم مستقیم آن را تشخیص می‌دهد بدون نیاز به هوش مصنوعی؛ اگر خالی بگذاری، هوش مصنوعی از روی متن درس حدس می‌زند. quiz_questions اختیاری است؛ دقیقاً یک گزینه‌ی هر سوال باید is_correct=true باشد."
}


@router.get("/content/smart-import/template")
async def get_smart_import_template(
    admin: AdminUser = Depends(require_content_editor()),
):
    return JSONResponse(SAMPLE_TEMPLATE)


@router.post("/content/smart-import/classify", response_model=ClassifyResponse)
async def classify_smart_import(
    file: UploadFile = File(...),
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فقط فایل JSON با فرمت مشخص‌شده پذیرفته می‌شود.")

    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فایل JSON معتبر نیست.")

    try:
        payload = RawLessonImportPayload.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"ساختار فایل نامعتبر است: {exc.errors()[0]['msg']}")

    lessons = [
        {"title": l.title, "body": l.body, "stage_name": l.stage_name, "department_name": l.department_name}
        for l in payload.lessons
    ]
    classifications = await classify_lessons(db, lessons)

    stages = db.query(JourneyStage).order_by(JourneyStage.display_order).all()
    department_types = db.query(StandardDepartmentType).order_by(
        StandardDepartmentType.macro_category, StandardDepartmentType.display_order
    ).all()

    items = [
        ClassifiedLessonItem(
            title=lesson["title"],
            body=lesson["body"],
            journey_stage_code=cls["journey_stage_code"],
            department_type_code=cls["department_type_code"],
            section_title=cls["section_title"],
            quiz_questions=raw_item.quiz_questions,
            error=cls["error"],
            matched_by_name=cls["matched_by_name"],
        )
        for lesson, cls, raw_item in zip(lessons, classifications, payload.lessons)
    ]

    return ClassifyResponse(
        stage_options=[{"code": s.code.value, "name": s.name} for s in stages],
        department_type_options=[{"code": d.code, "name": d.name} for d in department_types],
        items=items,
    )


@router.post("/content/smart-import/commit", response_model=SmartImportCommitSummaryResponse)
async def commit_smart_import(
    payload: SmartImportCommitPayload,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    for item in payload.items:
        if not item.journey_stage_code:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"برای درس «{item.title}» باید مرحله‌ی سفر بیمار مشخص شود.",
            )

    summary = run_smart_import_commit(db, payload)
    return SmartImportCommitSummaryResponse(**summary)