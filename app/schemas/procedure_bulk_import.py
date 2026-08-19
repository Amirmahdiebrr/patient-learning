# app/schemas/procedure_bulk_import.py
"""
app/schemas/procedure_bulk_import.py

Pydantic v2 DTOs for the smart bulk-import of the Procedure catalog.
Mirrors app/schemas/content_bulk_import.py (used for lessons) but
scoped to a single field per item (department_type_code), since a
Procedure needs nothing else besides a name + department type to be
created.
"""

from pydantic import BaseModel, Field


class RawProcedureImportItem(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)


class RawProcedureImportPayload(BaseModel):
    procedures: list[RawProcedureImportItem] = Field(min_length=1)


class ClassifiedProcedureItem(BaseModel):
    name: str
    department_type_code: str | None
    matched_by_name: bool = False
    error: str | None = None


class ProcedureClassifyResponse(BaseModel):
    department_type_options: list[dict]
    items: list[ClassifiedProcedureItem]


class ProcedureImportCommitItem(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    department_type_code: str = Field(min_length=1, max_length=100)


class ProcedureImportCommitPayload(BaseModel):
    items: list[ProcedureImportCommitItem] = Field(min_length=1)


class ProcedureImportCommitSummaryResponse(BaseModel):
    procedures_created: int
    procedures_updated: int
    errors: list[str]