# app/api/v1/admin_procedure_import.py
"""
app/api/v1/admin_procedure_import.py

Smart bulk-import for the Procedure catalog, mirroring
app/api/v1/admin_smart_import.py's classify/commit shape used for
lessons: the admin uploads a JSON file listing procedure names
(optionally with a department name each), the system tries to match
each one to a StandardDepartmentType by name, falls back to AI
classification for anything unmatched, the admin reviews/corrects the
result in the panel, and only then are the Procedure rows actually
created via /commit.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, RoleCode, StandardDepartmentType
from app.api.deps_admin import ScopeCheck
from app.schemas.procedure_bulk_import import (
    RawProcedureImportPayload, ProcedureClassifyResponse, ClassifiedProcedureItem,
    ProcedureImportCommitPayload, ProcedureImportCommitSummaryResponse,
)
from app.services.content_admin.procedure_classifier_service import classify_procedures
from app.services.content_admin.procedure_bulk_import_service import run_procedure_import_commit

router = APIRouter(prefix="/admin", tags=["admin_procedure_import"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))

SAMPLE_TEMPLATE = {
    "procedures": [
        {"name": "تعویض مفصل کامل زانو", "department_name": "ارتوپدی"},
        {"name": "آپاندکتومی", "department_name": "جراحی عمومی"},
        {"name": "TURP / تراش پروستات", "department_name": None},
    ],
    "_help": "برای هر عمل، نام آن را بنویس. اگر department_name را دقیق بنویسی، سیستم مستقیم آن را تشخیص می‌دهد؛ در غیر این صورت هوش مصنوعی بر اساس نام عمل حدس می‌زند و باید در مرحله‌ی بازبینی تایید یا اصلاح شود."
}


@router.get("/procedures/smart-import/template")
async def get_procedure_import_template(
    admin: AdminUser = Depends(require_content_editor()),
):
    return JSONResponse(SAMPLE_TEMPLATE)


@router.post("/procedures/smart-import/classify", response_model=ProcedureClassifyResponse)
async def classify_procedure_import(
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
        payload = RawProcedureImportPayload.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"ساختار فایل نامعتبر است: {exc.errors()[0]['msg']}")

    items = [{"name": p.name, "department_name": p.department_name} for p in payload.procedures]
    classifications = await classify_procedures(db, items)

    department_types = (
        db.query(StandardDepartmentType)
        .filter(StandardDepartmentType.is_active.is_(True))
        .order_by(StandardDepartmentType.macro_category, StandardDepartmentType.display_order)
        .all()
    )

    result_items = [
        ClassifiedProcedureItem(
            name=item["name"],
            department_type_code=cls["department_type_code"],
            matched_by_name=cls["matched_by_name"],
            error=cls["error"],
        )
        for item, cls in zip(items, classifications)
    ]

    return ProcedureClassifyResponse(
        department_type_options=[{"code": d.code, "name": d.name} for d in department_types],
        items=result_items,
    )


@router.post("/procedures/smart-import/commit", response_model=ProcedureImportCommitSummaryResponse)
async def commit_procedure_import(
    payload: ProcedureImportCommitPayload,
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    for item in payload.items:
        if not item.department_type_code:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"برای عمل «{item.name}» باید نوع بخش مشخص شود.",
            )

    summary = run_procedure_import_commit(db, payload)
    return ProcedureImportCommitSummaryResponse(**summary)