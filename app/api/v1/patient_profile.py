# app/api/v1/patient_profile.py
# app/api/v1/patient_profile.py
"""
app/api/v1/patient_profile.py

Patient-facing profile: view/edit personal info, upload avatar,
permanently delete own account. Scoped entirely by the AccessContext
cookie - no admin auth needed.

DELETE /patient-auth/account is patient-initiated, immediate, and
irreversible - see patient_account_service.delete_patient_account for
the full cascade. On success, all patient-facing cookies are cleared
exactly like logout, so the browser has no lingering session for a
now-nonexistent profile.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.templates import templates
from app.core.encryption import hash_lookup_value
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import PatientRegistration, PatientJourneyProfile
from app.api.deps import AccessContext, get_access_context, get_active_journey
from app.schemas.patient import PatientProfileResponse, PatientProfileUpdateRequest
from app.services.patient_account_service import delete_patient_account, PatientAccountDeletionError

router = APIRouter(tags=["patient_profile"])

AVATAR_ALLOWED_EXT = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".avif", ".jfif",
}
AVATAR_MAGIC_BYTES = {
    ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".jfif": b"\xff\xd8\xff",
    ".png": b"\x89PNG", ".gif": b"GIF8", ".bmp": b"BM",
}
AVATAR_FTYP_BASED_EXT = {".heic", ".heif", ".avif"}
AVATAR_MAX_BYTES = 15 * 1024 * 1024


def _get_registration(db: Session, profile_id: uuid.UUID) -> PatientRegistration:
    registration = (
        db.query(PatientRegistration)
        .filter(PatientRegistration.patient_access_profile_id == profile_id)
        .first()
    )
    if not registration:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اطلاعات هویتی پیدا نشد.")
    return registration


def _to_response(
    registration: PatientRegistration, context: AccessContext, journey: PatientJourneyProfile,
) -> PatientProfileResponse:
    return PatientProfileResponse(
        first_name=registration.first_name,
        last_name=registration.last_name,
        national_id=registration.national_id,
        phone_number=registration.phone_number,
        insurance_code=registration.insurance_code,
        avatar_url=registration.avatar_url,
        hospital_name=context.hospital.name,
        department_name=context.department.name,
        current_stage_name=journey.current_stage.value if journey else None,
        disease_name=journey.disease.name if journey and journey.disease else None,
        treatment_name=journey.treatment.name if journey and journey.treatment else None,
        procedure_name=journey.procedure.name if journey and journey.procedure else None,
        age=journey.age if journey else None,
        gender=journey.gender if journey else None,
        has_surgery=journey.has_surgery if journey else None,
        member_since=registration.created_at,
    )


def _avatar_content_matches_extension(ext: str, contents: bytes) -> bool:
    if ext in AVATAR_MAGIC_BYTES:
        return contents.startswith(AVATAR_MAGIC_BYTES[ext])
    if ext == ".webp":
        return len(contents) >= 12 and contents[0:4] == b"RIFF" and contents[8:12] == b"WEBP"
    if ext in AVATAR_FTYP_BASED_EXT:
        return len(contents) >= 8 and contents[4:8] == b"ftyp"
    if ext in (".tiff", ".tif"):
        return contents.startswith(b"II*\x00") or contents.startswith(b"MM\x00*")
    return True


@router.get("/profile")
async def profile_page(
    request: Request,
    context: AccessContext = Depends(get_access_context),
):
    return templates.TemplateResponse(request, "patient_profile.html", {"request": request})


@router.get("/patient-auth/profile", response_model=PatientProfileResponse)
async def get_profile(
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    registration = _get_registration(db, context.patient_profile.id)
    return _to_response(registration, context, journey)


@router.patch("/patient-auth/profile", response_model=PatientProfileResponse)
async def update_profile(
    payload: PatientProfileUpdateRequest,
    context: AccessContext = Depends(get_access_context),
    journey: PatientJourneyProfile = Depends(get_active_journey),
    db: Session = Depends(get_db),
):
    registration = _get_registration(db, context.patient_profile.id)

    registration.first_name = payload.first_name
    registration.last_name = payload.last_name
    registration.phone_number = payload.phone_number
    registration.phone_number_hash = hash_lookup_value(payload.phone_number)
    registration.insurance_code = payload.insurance_code

    if payload.age is not None:
        journey.age = payload.age
    if payload.gender is not None:
        journey.gender = payload.gender

    db.commit()
    db.refresh(registration)
    db.refresh(journey)

    return _to_response(registration, context, journey)


@router.post("/patient-auth/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    registration = _get_registration(db, context.patient_profile.id)

    original_name = file.filename or "avatar"
    ext = os.path.splitext(original_name)[1].lower()

    if ext not in AVATAR_ALLOWED_EXT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فرمت تصویر مجاز نیست.")

    contents = await file.read()
    if len(contents) > AVATAR_MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "حجم تصویر نباید بیشتر از ۱۵ مگابایت باشد.")

    if not _avatar_content_matches_extension(ext, contents):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "محتوای فایل با پسوند آن مطابقت ندارد.")

    os.makedirs(settings.MEDIA_UPLOAD_DIR, exist_ok=True)
    stored_filename = f"avatar_{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(settings.MEDIA_UPLOAD_DIR, stored_filename)

    with open(stored_path, "wb") as out_file:
        out_file.write(contents)

    registration.avatar_url = f"/static/uploads/{stored_filename}"
    db.commit()

    return JSONResponse({"avatar_url": registration.avatar_url})


@router.delete("/patient-auth/account")
async def delete_own_account(
    response: Response,
    context: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
):
    try:
        delete_patient_account(db, context.patient_profile.id)
    except PatientAccountDeletionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    response.delete_cookie(settings.PATIENT_PROFILE_COOKIE_NAME)
    response.delete_cookie(settings.ACCESS_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)

    return JSONResponse({"ok": True})