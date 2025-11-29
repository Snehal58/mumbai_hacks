"""Workout collection schema."""

from typing import Dict
from pydantic import BaseModel, Field
from datetime import datetime
from models.schemas import WorkoutType

class PlanItem(BaseModel):
    name: str = Field(..., description="Workout name")
    sets: float = Field(..., description="Number of sets")

class Workout(BaseModel):
    """Workout collection model."""
    user_id: str = Field(..., description="User identifier")
    date: datetime = Field(..., description="Workout date")
    type: WorkoutType = Field(..., description="Workout type: upper, lower, or full body")
    repetitions: int = Field(..., description="Number of repetitions")
    expiry: datetime | None = Field(None, description="Validity of the workout")
    plan: list[PlanItem] = Field(..., description="Name and sets included in the workout")
    is_temp: bool = Field(..., description="Whether the workout is added for a short duration of time")

