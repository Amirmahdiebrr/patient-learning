# app/schemas/ghost.py
"""
app/schemas/ghost.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GhostSessionCreateRequest(BaseModel):
    hospital_id: uuid.UUID
    department_id: uuid.UUID
    ghost_label: str | None = Field(default=None, max_length=255)

    disease_id: uuid.UUID | None = None
    treatment_id: uuid.UUID | None = None
    procedure_id: uuid.UUID | None = None
    has_surgery: bool | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None
    target_stage_code: str | None = None


class GhostSessionEnterResponse(BaseModel):
    redirect_url: str = "/home"


class GhostSessionRowResponse(BaseModel):
    id: uuid.UUID
    ghost_label: str | None
    hospital_name: str
    department_name: str
    current_stage: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GhostSessionListResponse(BaseModel):
    rows: list[GhostSessionRowResponse]


class GhostJumpStageRequest(BaseModel):
    target_stage_code: str