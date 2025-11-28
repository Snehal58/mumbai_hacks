"""Workout logs collection schema."""

from pydantic import BaseModel, Field
from datetime import datetime


class WorkoutLog(BaseModel):
    """Workout logs collection model."""
    user_id: str = Field(..., description="User identifier")
    date: datetime = Field(..., description="Workout log date")
    type: str = Field(..., description="Workout type")
    plan: str = Field(..., description="Workout plan")
    is_extra: bool = Field(..., description="Whether this is an extra workout")

