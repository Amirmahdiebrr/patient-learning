# scripts/seed_department_types.py
"""
scripts/seed_department_types.py

Idempotent seed script for the standard Iranian hospital department
taxonomy (StandardDepartmentType). Run once (or re-run safely anytime).

nicu_parent_education/picu_parent_education duplicate the NICU/PICU
critical-care department types and are kept deactivated
(is_active=False) so they no longer appear as selectable departments;
parent-education content for NICU/PICU patients belongs under the
NICU/PICU department types themselves.

Run with:
    python -m scripts.seed_department_types
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import StandardDepartmentType, DepartmentMacroCategory
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


DEPARTMENT_TYPES = [
    (DepartmentMacroCategory.SURGICAL, "general_surgery", "جراحی عمومی", 1),
    (DepartmentMacroCategory.SURGICAL, "orthopedics", "ارتوپدی", 2),
    (DepartmentMacroCategory.SURGICAL, "urology", "اورولوژی", 3),
    (DepartmentMacroCategory.SURGICAL, "gynecology_surgery", "جراحی زنان و زایمان", 4),
    (DepartmentMacroCategory.SURGICAL, "ent", "گوش، حلق و بینی (ENT)", 5),
    (DepartmentMacroCategory.SURGICAL, "ophthalmology", "چشم‌پزشکی", 6),
    (DepartmentMacroCategory.SURGICAL, "neurosurgery", "جراحی مغز و اعصاب", 7),
    (DepartmentMacroCategory.SURGICAL, "cardiac_surgery", "جراحی قلب و عروق", 8),
    (DepartmentMacroCategory.SURGICAL, "plastic_surgery", "جراحی پلاستیک و ترمیمی", 9),
    (DepartmentMacroCategory.SURGICAL, "maxillofacial_surgery", "جراحی فک و صورت", 10),

    (DepartmentMacroCategory.MEDICAL, "general_medicine", "داخلی عمومی", 1),
    (DepartmentMacroCategory.MEDICAL, "cardiology", "قلب غیرجراحی", 2),
    (DepartmentMacroCategory.MEDICAL, "gastroenterology", "گوارش و کبد", 3),
    (DepartmentMacroCategory.MEDICAL, "endocrinology", "غدد و دیابت", 4),
    (DepartmentMacroCategory.MEDICAL, "nephrology", "کلیه و دیالیز", 5),
    (DepartmentMacroCategory.MEDICAL, "pulmonology", "ریه", 6),
    (DepartmentMacroCategory.MEDICAL, "neurology", "نورولوژی (مغز و اعصاب داخلی)", 7),
    (DepartmentMacroCategory.MEDICAL, "infectious_disease", "عفونی", 8),
    (DepartmentMacroCategory.MEDICAL, "oncology_hematology", "آنکولوژی / هماتولوژی", 9),
    (DepartmentMacroCategory.MEDICAL, "toxicology", "مسمومیت", 10),

    (DepartmentMacroCategory.CRITICAL_CARE, "icu", "ICU", 1),
    (DepartmentMacroCategory.CRITICAL_CARE, "ccu", "CCU", 2),
    (DepartmentMacroCategory.CRITICAL_CARE, "nicu", "NICU", 3),
    (DepartmentMacroCategory.CRITICAL_CARE, "picu", "PICU", 4),
    (DepartmentMacroCategory.CRITICAL_CARE, "emergency", "اورژانس", 5),

    (DepartmentMacroCategory.OBSTETRICS_GYNECOLOGY, "vaginal_delivery", "زایمان طبیعی", 1),
    (DepartmentMacroCategory.OBSTETRICS_GYNECOLOGY, "cesarean", "سزارین", 2),
    (DepartmentMacroCategory.OBSTETRICS_GYNECOLOGY, "high_risk_pregnancy", "بستری بارداری پرخطر", 3),
    (DepartmentMacroCategory.OBSTETRICS_GYNECOLOGY, "gynecology_medical", "بیماری‌های زنان (غیرجراحی)", 4),

    (DepartmentMacroCategory.PEDIATRICS, "general_pediatrics", "اطفال عمومی", 1),
    (DepartmentMacroCategory.PEDIATRICS, "pediatric_surgery", "اطفال جراحی", 2),
    (DepartmentMacroCategory.PEDIATRICS, "nicu_parent_education", "NICU (آموزش والدین)", 3),
    (DepartmentMacroCategory.PEDIATRICS, "picu_parent_education", "PICU (آموزش والدین)", 4),

    (DepartmentMacroCategory.OUTPATIENT_PROCEDURES, "angiography", "آنژیوگرافی / کت‌لب", 1),
    (DepartmentMacroCategory.OUTPATIENT_PROCEDURES, "upper_endoscopy", "اندوسکوپی فوقانی", 2),
    (DepartmentMacroCategory.OUTPATIENT_PROCEDURES, "colonoscopy", "کولونوسکوپی", 3),
    (DepartmentMacroCategory.OUTPATIENT_PROCEDURES, "outpatient_chemotherapy", "شیمی‌درمانی سرپایی", 4),
    (DepartmentMacroCategory.OUTPATIENT_PROCEDURES, "outpatient_dialysis", "دیالیز سرپایی", 5),
]

# Duplicate of NICU/PICU critical-care departments - kept inactive.
INACTIVE_CODES = {"nicu_parent_education", "picu_parent_education"}


def main():
    db = SessionLocal()
    try:
        for macro_category, code, name, order in DEPARTMENT_TYPES:
            is_active = code not in INACTIVE_CODES
            existing = db.query(StandardDepartmentType).filter(StandardDepartmentType.code == code).first()
            if existing:
                existing.name = name
                existing.macro_category = macro_category
                existing.display_order = order
                existing.is_active = is_active
            else:
                db.add(StandardDepartmentType(
                    macro_category=macro_category, code=code, name=name,
                    display_order=order, is_active=is_active,
                ))
        db.commit()
        logger.info(f"[Seed] standard_department_types: {len(DEPARTMENT_TYPES)} row(s) upserted")
    finally:
        db.close()


if __name__ == "__main__":
    main()