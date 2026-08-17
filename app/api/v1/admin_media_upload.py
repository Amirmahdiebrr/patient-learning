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
    "image": {
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif",
        ".heic", ".heif", ".avif", ".svg", ".jfif", ".ico",
    },
    "video": {".mp4", ".webm", ".mov", ".ogg", ".mkv", ".avi", ".m4v", ".3gp"},
    "pdf": {".pdf"},
    "animation": {".gif", ".webp", ".mp4", ".apng"},
}

# Fixed-prefix signatures - checked with a simple startswith().
_FIXED_MAGIC_BYTES = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".jfif": b"\xff\xd8\xff",
    ".png": b"\x89PNG",
    ".gif": b"GIF8",
    ".pdf": b"%PDF",
    ".ogg": b"OggS",
    ".webm": b"\x1a\x45\xdf\xa3",  # EBML header (Matroska/WebM container)
    ".mkv": b"\x1a\x45\xdf\xa3",
    ".bmp": b"BM",
    ".ico": b"\x00\x00\x01\x00",
}

# ISO-base-media-container formats: the actual type is signalled by a
# 4-byte brand at offset 8, not by the first bytes - so all of these
# just need bytes 4:8 to be "ftyp". Covers standard video containers
# AND modern image containers like HEIC/HEIF/AVIF (iPhone photos).
_FTYP_BASED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".3gp", ".heic", ".heif", ".avif"}


def _content_matches_extension(ext: str, contents: bytes) -> bool:
    """
    Validates the file's actual bytes against its declared extension
    where a reliable signature exists. Formats without a simple fixed
    signature (svg, tiff, and anything not explicitly listed) fall
    through to `True` - the extension whitelist above is already the
    real gatekeeper; this is just an extra check for the common cases
    where a mismatch is easy to detect.
    """
    if ext in _FIXED_MAGIC_BYTES:
        return contents.startswith(_FIXED_MAGIC_BYTES[ext])

    if ext == ".webp":
        # RIFF <4-byte size> WEBP
        return len(contents) >= 12 and contents[0:4] == b"RIFF" and contents[8:12] == b"WEBP"

    if ext in _FTYP_BASED_EXTENSIONS:
        return len(contents) >= 8 and contents[4:8] == b"ftyp"

    if ext in (".tiff", ".tif"):
        return contents.startswith(b"II*\x00") or contents.startswith(b"MM\x00*")

    # svg, apng, and any other extension without a simple fixed
    # signature - the extension whitelist already restricts what can
    # reach this point, so allow it through.
    return True


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

    if not _content_matches_extension(ext, contents):
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