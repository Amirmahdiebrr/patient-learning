"""
app/api/v1/admin_smart_import.py

"Smart import": the admin writes all lessons in one file (just title
+ body per lesson - no stage/department metadata) and uploads it.
Step 1 (/classify) asks the AI to guess each lesson's journey stage +
department type + section label; the admin reviews/edits those
suggestions in the panel. Step 2 (/commit) actually creates the
sections/lessons from the (possibly edited) list. The AI only
classifies placement - it never writes or alters lesson content.
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
            "body": "متن کامل درسی که خودت نوشته‌ای اینجا قرار می‌گیرد..."
        },
        {
            "title": "آماده‌سازی قبل از سزارین",
            "body": "متن کامل این درس..."
        }
    ],
    "_help": "فقط عنوان و متن هر درس را بنویس؛ مرحله و نوع بخش را خودت مشخص نکن - هوش مصنوعی آن را تشخیص می‌دهد و بعد از آپلود می‌توانی نتیجه را ویرایش کنی."
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

    lessons = [{"title": l.title, "body": l.body} for l in payload.lessons]
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
            error=cls["error"],
        )
        for lesson, cls in zip(lessons, classifications)
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