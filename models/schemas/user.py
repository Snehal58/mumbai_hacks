"""User collection schema."""

from pydantic import BaseModel, Field
from models.schemas.enums import GoalType


class User(BaseModel):
    """User collection model."""
    user_id: str = Field(..., description="Unique user identifier")
    weight: float = Field(..., description="User weight in kg")
    height: float = Field(..., description="User height in cm")
    BMI: float = Field(..., description="Body Mass Index")
    goal: GoalType = Field(..., description="User goal: muscle gain or fat loss")

