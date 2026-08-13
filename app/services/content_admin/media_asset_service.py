"""
app/services/content_admin/media_asset_service.py
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import MediaAsset, MediaType, Lesson
from app.services.content_admin.errors import ContentNotFoundError


def create_media_asset(
    db: Session, lesson_id: uuid.UUID, media_type: str, file_url: str,
    thumbnail_url: str | None, duration_seconds: int | None, display_order: int,
) -> MediaAsset:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise ContentNotFoundError("درس پیدا نشد.")

    media = MediaAsset(
        lesson_id=lesson_id, type=MediaType(media_type), file_url=file_url,
        thumbnail_url=thumbnail_url, duration_seconds=duration_seconds,
        display_order=display_order,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def list_media_assets(db: Session, lesson_id: uuid.UUID) -> list[MediaAsset]:
    return db.query(MediaAsset).filter(MediaAsset.lesson_id == lesson_id).order_by(MediaAsset.display_order).all()


def delete_media_asset(db: Session, media_id: uuid.UUID) -> None:
    media = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not media:
        raise ContentNotFoundError("فایل پیدا نشد.")
    db.delete(media)
    db.commit()