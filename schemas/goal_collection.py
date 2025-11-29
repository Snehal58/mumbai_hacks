"""Goal collection schema."""

from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class GoalCollection(BaseModel):
    """Goal collection model."""
    user_id: str = Field(..., description="User identifier")
    goal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_name: str = Field(..., description="Name of the goal")
    start_date: datetime = Field(..., description="Goal start date")
    end_date: datetime = Field(..., description="Goal end date")
    target_weight: float = Field(..., description="Target weight in kg")
    workout_skipped: int = Field(default=0, description="Number of workouts skipped")
    cheat_meals: int = Field(default=0, description="Number of cheat meals")
    extra_workouts: int = Field(default=0, description="Number of extra workouts")
    avg_daily_burn: float = Field(default=0.0, description="Average daily calories burned")
    avg_consumption: float = Field(default=0.0, description="Average daily calories consumed")
    avg_protein: float = Field(default=0.0, description="Average daily protein intake in grams")
    consistency_percentage: float = Field(default=0.0, description="Consistency percentage")

