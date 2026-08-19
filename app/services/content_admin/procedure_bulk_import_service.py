# app/services/content_admin/procedure_bulk_import_service.py
"""
app/services/content_admin/procedure_bulk_import_service.py

Commits a reviewed, fully-classified batch of procedures. For each
item, resolves the target StandardDepartmentType by its code, then
finds-or-updates a Procedure row scoped to that department type by
slug (same idempotent find-or-update pattern used for lessons in
smart_import_commit_service.py) so re-running an import file never
creates duplicates.
"""

from app.infrastructure.db.models import StandardDepartmentType, Procedure
from app.schemas.content_admin import slugify
from app.schemas.procedure_bulk_import import ProcedureImportCommitPayload


def _find_or_create_procedure(db, department_type_id, name: str) -> tuple[Procedure, bool]:
    slug = slugify(name)
    existing = (
        db.query(Procedure)
        .filter(Procedure.department_type_id == department_type_id, Procedure.slug == slug)
        .first()
    )
    if existing:
        existing.name = name
        existing.is_active = True
        db.flush()
        return existing, False

    next_order = (
        db.query(Procedure)
        .filter(Procedure.department_type_id == department_type_id)
        .count()
    ) + 1

    procedure = Procedure(
        department_type_id=department_type_id,
        name=name,
        slug=slug,
        display_order=next_order,
    )
    db.add(procedure)
    db.flush()
    return procedure, True


def run_procedure_import_commit(db, payload: ProcedureImportCommitPayload) -> dict:
    summary = {"procedures_created": 0, "procedures_updated": 0, "errors": []}

    for item in payload.items:
        dept_type = (
            db.query(StandardDepartmentType)
            .filter(StandardDepartmentType.code == item.department_type_code)
            .first()
        )
        if not dept_type:
            summary["errors"].append(f"عمل «{item.name}»: نوع بخش «{item.department_type_code}» پیدا نشد.")
            continue

        _, created = _find_or_create_procedure(db, dept_type.id, item.name)
        summary["procedures_created" if created else "procedures_updated"] += 1

    db.commit()
    return summary