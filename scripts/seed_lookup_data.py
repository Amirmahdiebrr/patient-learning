"""
scripts/seed_lookup_data.py

One-time (idempotent) seed script:
- journey_stages: fixed 12-row lookup table (never created via admin panel)
- roles: fixed 5-row lookup table
- optionally bootstraps the first super_admin from env vars

Run with:
    python -m scripts.seed_lookup_data
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal, Base, engine
from app.infrastructure.db.models import (
    JourneyStage, JourneyStageCode,
    Role, RoleCode,
    AdminUser, AdminRoleAssignment,
)
from app.core.security import hash_password
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


JOURNEY_STAGES = [
    (JourneyStageCode.WELCOME, "خوش‌آمدگویی", 1),
    (JourneyStageCode.GENERAL_EDUCATION, "آموزش عمومی بیمارستان", 2),
    (JourneyStageCode.DEPARTMENT_INTRO, "معرفی بخش", 3),
    (JourneyStageCode.ADMISSION, "بستری / پذیرش", 4),
    (JourneyStageCode.BEFORE_PROCEDURE, "قبل از عمل", 5),
    (JourneyStageCode.PROCEDURE, "حین عمل", 6),
    (JourneyStageCode.AFTER_PROCEDURE, "بعد از عمل", 7),
    (JourneyStageCode.DAILY_INPATIENT, "آموزش روزانه‌ی بستری", 8),
    (JourneyStageCode.DISCHARGE, "ترخیص", 9),
    (JourneyStageCode.HOME_CARE, "مراقبت در منزل", 10),
    (JourneyStageCode.FOLLOW_UP, "پیگیری", 11),
    (JourneyStageCode.LONG_TERM_MONITORING, "پایش بلندمدت", 12),
]

ROLES = [
    (RoleCode.SUPER_ADMIN, "ادمین کل پلتفرم"),
    (RoleCode.HOSPITAL_ADMIN, "ادمین بیمارستان"),
    (RoleCode.DEPARTMENT_ADMIN, "ادمین بخش"),
    (RoleCode.DOCTOR, "پزشک"),
    (RoleCode.CONTENT_MANAGER, "مدیر محتوا"),
]


def seed_journey_stages(db):
    for code, name, order in JOURNEY_STAGES:
        existing = db.query(JourneyStage).filter(JourneyStage.code == code).first()
        if existing:
            existing.name = name
            existing.display_order = order
        else:
            db.add(JourneyStage(code=code, name=name, display_order=order))
    db.commit()
    logger.info(f"[Seed] journey_stages: {len(JOURNEY_STAGES)} row(s) upserted")


def seed_roles(db):
    for code, name in ROLES:
        existing = db.query(Role).filter(Role.code == code).first()
        if existing:
            existing.name = name
        else:
            db.add(Role(code=code, name=name))
    db.commit()
    logger.info(f"[Seed] roles: {len(ROLES)} row(s) upserted")


def seed_bootstrap_super_admin(db):
    from app.core.config import settings

    email = settings.BOOTSTRAP_SUPER_ADMIN_EMAIL
    password = settings.BOOTSTRAP_SUPER_ADMIN_PASSWORD

    if not email or not password:
        logger.info("[Seed] Skipped super_admin bootstrap (BOOTSTRAP_SUPER_ADMIN_EMAIL/PASSWORD not set)")
        return

    existing = db.query(AdminUser).filter(AdminUser.email == email.lower()).first()
    if existing:
        logger.info(f"[Seed] super_admin '{email}' already exists, skipping")
        return

    admin = AdminUser(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name="Platform Super Admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    super_admin_role = db.query(Role).filter(Role.code == RoleCode.SUPER_ADMIN).first()
    db.add(AdminRoleAssignment(admin_user_id=admin.id, role_id=super_admin_role.id))
    db.commit()

    logger.info(f"[Seed] Bootstrapped super_admin: {email}")


def main():
    Base.metadata.create_all(bind=engine)  # dev convenience; production uses Alembic

    db = SessionLocal()
    try:
        seed_journey_stages(db)
        seed_roles(db)
        seed_bootstrap_super_admin(db)
        logger.info("[Seed] Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()