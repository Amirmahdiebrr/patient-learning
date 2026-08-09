"""
app/services/event_handlers/followup_handlers.py

Subscribes to PatientDischarged and schedules a default SMS
follow-up. Uses its own DB session, same pattern as audit_handlers.
"""

from app.core.event_bus import event_bus
from app.core.events import PatientDischarged
from app.infrastructure.db.session import SessionLocal
from app.services.followup.followup_scheduler import schedule_followup

DEFAULT_FOLLOWUP_DELAY_DAYS = 3


def _on_patient_discharged(event: PatientDischarged) -> None:
    db = SessionLocal()
    try:
        schedule_followup(
            db,
            patient_access_profile_id=event.patient_access_profile_id,
            hospital_id=event.hospital_id,
            delay_days=DEFAULT_FOLLOWUP_DELAY_DAYS,
        )
    finally:
        db.close()


def register_followup_handlers() -> None:
    event_bus.subscribe(PatientDischarged, _on_patient_discharged)