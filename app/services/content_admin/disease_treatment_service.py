"""
app/services/content_admin/disease_treatment_service.py

Disease -> Treatment CRUD (create + active listing only - no
update/deactivate exposed yet, matching the original behavior).
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import Disease, Treatment
from app.schemas.content_admin import slugify
from app.services.content_admin.errors import ContentNotFoundError


def create_disease(db: Session, name: str, description: str | None) -> Disease:
    disease = Disease(name=name, slug=slugify(name), description=description)
    db.add(disease)
    db.commit()
    db.refresh(disease)
    return disease


def list_active_diseases(db: Session) -> list[Disease]:
    return db.query(Disease).filter(Disease.is_active.is_(True)).order_by(Disease.name).all()


def create_treatment(db: Session, disease_id: uuid.UUID, name: str, description: str | None) -> Treatment:
    disease = db.query(Disease).filter(Disease.id == disease_id).first()
    if not disease:
        raise ContentNotFoundError("بیماری پیدا نشد.")

    treatment = Treatment(disease_id=disease.id, name=name, slug=slugify(name), description=description)
    db.add(treatment)
    db.commit()
    db.refresh(treatment)
    return treatment


def list_active_treatments(db: Session, disease_id: uuid.UUID) -> list[Treatment]:
    return (
        db.query(Treatment)
        .filter(Treatment.disease_id == disease_id, Treatment.is_active.is_(True))
        .order_by(Treatment.name)
        .all()
    )