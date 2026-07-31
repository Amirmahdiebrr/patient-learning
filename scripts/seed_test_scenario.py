"""
scripts/seed_test_scenario.py

Idempotent-ish seed script for manual end-to-end testing:
hospital -> department -> disease -> treatment -> QR access point
-> education section -> lesson -> media asset -> quiz question.

Run with:
    python -m scripts.seed_test_scenario
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import (
    Hospital, Department, Disease, Treatment,
    JourneyStage, JourneyStageCode,
    EducationSection, Lesson, MediaAsset, MediaType,
    QuizQuestion, QuizOption,
    QRAccessPoint, QRAccessPointStatus,
)
from app.services.access_gate_service import generate_qr_token
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    db = SessionLocal()
    try:
        hospital = Hospital(name="بیمارستان تست", slug="test-hospital")
        db.add(hospital)
        db.flush()

        department = Department(hospital_id=hospital.id, name="بخش ارتوپدی", slug="ortho")
        db.add(department)
        db.flush()

        disease = Disease(name="شکستگی زانو", slug="knee-fracture")
        db.add(disease)
        db.flush()

        treatment = Treatment(disease_id=disease.id, name="جراحی تعویض زانو", slug="knee-replacement")
        db.add(treatment)
        db.flush()

        admission_stage = db.query(JourneyStage).filter(
            JourneyStage.code == JourneyStageCode.ADMISSION
        ).first()
        if not admission_stage:
            logger.error("journey_stages خالیه - اول scripts/seed_lookup_data.py رو اجرا کن.")
            return

        section = EducationSection(
            journey_stage_id=admission_stage.id,
            treatment_id=treatment.id,
            title="آماده‌سازی برای بستری",
            display_order=1,
        )
        db.add(section)
        db.flush()

        lesson = Lesson(
            section_id=section.id,
            title="چه چیزهایی برای بستری همراه بیاورم؟",
            body_richtext="لباس راحت، مدارک بیمه، داروهای فعلی خود را همراه داشته باشید.",
            display_order=1,
            is_published=True,
        )
        db.add(lesson)
        db.flush()

        db.add(MediaAsset(
            lesson_id=lesson.id,
            type=MediaType.IMAGE,
            file_url="https://picsum.photos/seed/curalink/800/450",
            display_order=1,
        ))

        question = QuizQuestion(
            lesson_id=lesson.id,
            question_text="کدام مورد باید همراه بیمار باشد؟",
            display_order=1,
        )
        db.add(question)
        db.flush()

        db.add(QuizOption(question_id=question.id, option_text="مدارک بیمه", is_correct=True, display_order=1))
        db.add(QuizOption(question_id=question.id, option_text="لپ‌تاپ شخصی", is_correct=False, display_order=2))

        qr = QRAccessPoint(
            hospital_id=hospital.id,
            department_id=department.id,
            access_token=generate_qr_token(),
            label="ورودی بخش ارتوپدی - تست",
            status=QRAccessPointStatus.ACTIVE,
        )
        db.add(qr)

        db.commit()

        logger.info("=" * 60)
        logger.info(f"Hospital ID:   {hospital.id}")
        logger.info(f"Lesson ID:     {lesson.id}")
        logger.info(f"QR token:      {qr.access_token}")
        logger.info(f"Entry URL:     http://127.0.0.1:8000/entry?token={qr.access_token}")
        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()