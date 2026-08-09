"""
app/schemas/patient_journey_admin.py
"""

from pydantic import BaseModel


class JourneyStageTransitionRequest(BaseModel):
    target_stage: str


class JourneyStageResponse(BaseModel):
    current_stage: str