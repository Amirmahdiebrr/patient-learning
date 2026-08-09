"""
app/api/v1/admin_media_upload.py
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status

from app.core.config import settings
from app.infrastructure.db.models import AdminUser, RoleCode
from app.schemas.content_admin import MediaUploadResponse
from app.api.deps_admin import ScopeCheck

router = APIRouter(prefix="/admin", tags=["admin_media_upload"])

require_content_editor = ScopeCheck(allowed_roles=(RoleCode.SUPER_ADMIN, RoleCode.CONTENT_MANAGER))

ALLOWED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".gif"},
    "video": {".mp4", ".webm", ".mov", ".ogg"},
    "pdf": {".pdf"},
    "animation": {".gif", ".webp", ".mp4"},
}

MAGIC_BYTES = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG",
    ".gif": b"GIF8",
    ".pdf": b"%PDF",
}


@router.post("/media-upload", response_model=MediaUploadResponse)
async def upload_media_file(
    media_type: str = Form(...),
    file: UploadFile = File(...),
    admin: AdminUser = Depends(require_content_editor()),
):
    if media_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "نوع مدیا نامعتبر است.")

    original_name = file.filename or "upload"
    ext = os.path.splitext(original_name)[1].lower()

    if ".." in original_name or "/" in original_name or "\\" in original_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "نام فایل نامعتبر است.")

    if ext not in ALLOWED_EXTENSIONS[media_type]:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS[media_type]))
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"پسوند فایل برای نوع '{media_type}' مجاز نیست. پسوندهای مجاز: {allowed}",
        )

    max_bytes = settings.MEDIA_MAX_UPLOAD_MB * 1024 * 1024
    contents = await file.read()

    if len(contents) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"حجم فایل نباید بیشتر از {settings.MEDIA_MAX_UPLOAD_MB} مگابایت باشد.",
        )

    expected_magic = MAGIC_BYTES.get(ext)
    if expected_magic and not contents.startswith(expected_magic):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "محتوای فایل با پسوند آن مطابقت ندارد.")

    os.makedirs(settings.MEDIA_UPLOAD_DIR, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(settings.MEDIA_UPLOAD_DIR, stored_filename)

    real_upload_dir = os.path.realpath(settings.MEDIA_UPLOAD_DIR)
    real_stored_path = os.path.realpath(stored_path)
    if not real_stored_path.startswith(real_upload_dir):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مسیر ذخیره‌سازی نامعتبر است.")

    with open(stored_path, "wb") as out_file:
        out_file.write(contents)

    return MediaUploadResponse(
        url=f"/static/uploads/{stored_filename}",
        original_filename=original_name,
        size_bytes=len(contents),
    )