"""
app/api/v1/admin_content_export.py
"""

import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import AdminUser, RoleCode
from app.api.deps_admin import ScopeCheck
from app.services.content_admin.content_export_service import (
    collect_export_data, build_markdown_files, build_json_files, build_zip,
)

router = APIRouter(prefix="/admin", tags=["admin_content_export"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))


@router.get("/content/export")
async def export_content(
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    split_by: str = Query("none", pattern="^(none|stage|department)$"),
    include_drafts: bool = Query(True),
    admin: AdminUser = Depends(require_content_editor()),
    db: Session = Depends(get_db),
):
    data = collect_export_data(db, include_drafts=include_drafts)
    files = build_markdown_files(data, split_by) if format == "markdown" else build_json_files(data, split_by)

    if len(files) == 1:
        filename, content = next(iter(files.items()))
        media_type = "text/markdown; charset=utf-8" if format == "markdown" else "application/json"
        return Response(
            content=content.encode("utf-8"),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    zip_bytes = build_zip(files)
    zip_filename = f"curalink-content-export-{split_by}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )