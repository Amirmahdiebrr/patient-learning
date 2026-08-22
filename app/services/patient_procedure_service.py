"""
app/services/patient_procedure_service.py

Lets a patient pick one or more procedures relevant to them (beyond
the single procedure_id chosen at onboarding), editable any time from
their own profile page. get_effective_procedure_ids() is the single
entry point content_targeting_service uses to resolve
before/after-procedure education: it unions the patient's explicit
selections with the legacy single onboarding procedure_id, so nothing
regresses for patients who never touch the new picker.
"""

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.db.models import PatientProcedureSelection, Procedure, PatientJourneyProfile


def get_selected_procedure_ids(db: Session, patient_access_profile_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        db.query(PatientProcedureSelection.procedure_id)
        .filter(PatientProcedureSelection.patient_access_profile_id == patient_access_profile_id)
        .all()
    )
    return [r[0] for r in rows]


def get_selected_procedures(db: Session, patient_access_profile_id: uuid.UUID) -> list[Procedure]:
    return (
        db.query(Procedure)
        .join(PatientProcedureSelection, PatientProcedureSelection.procedure_id == Procedure.id)
        .filter(PatientProcedureSelection.patient_access_profile_id == patient_access_profile_id)
        .order_by(Procedure.display_order, Procedure.name)
        .all()
    )


def get_effective_procedure_ids(db: Session, journey: PatientJourneyProfile) -> list[uuid.UUID]:
    selected = get_selected_procedure_ids(db, journey.patient_access_profile_id)
    if journey.procedure_id and journey.procedure_id not in selected:
        selected.append(journey.procedure_id)
    return selected


def set_selected_procedures(
    db: Session,
    patient_access_profile_id: uuid.UUID,
    department_type_id: uuid.UUID | None,
    procedure_ids: list[uuid.UUID],
) -> list[Procedure]:
    valid_procedures: list[Procedure] = []
    if department_type_id and procedure_ids:
        valid_procedures = (
            db.query(Procedure)
            .filter(
                Procedure.id.in_(procedure_ids),
                Procedure.department_type_id == department_type_id,
                Procedure.is_active.is_(True),
            )
            .all()
        )

    db.query(PatientProcedureSelection).filter(
        PatientProcedureSelection.patient_access_profile_id == patient_access_profile_id
    ).delete(synchronize_session=False)

    for procedure in valid_procedures:
        db.add(PatientProcedureSelection(
            patient_access_profile_id=patient_access_profile_id,
            procedure_id=procedure.id,
        ))

    db.commit()
    return valid_procedures