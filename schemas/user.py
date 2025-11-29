"""User collection schema."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from .enums import GoalType

class User(BaseModel):
    """User collection model."""
    user_id: str = Field(..., description="Unique user identifier")
    weight: Optional[float] = Field(None, description="User weight in kg")
    height: Optional[float] = Field(None, description="User height in cm")
    bmi: Optional[float] = Field(None, description="Body Mass Index")
    goal: Optional[GoalType] = Field(None, description="User goal: muscle gain or fat loss")
    questionnaire: Optional[Dict[str, Any]] = Field(None, description="Questionnaire answers from planner agent")
    meal_plan: Optional[Dict[str, Any]] = Field(None, description="Generated meal plan")
    session_id: Optional[str] = Field(None, description="Current session identifier")
    finalize_diet_plan: Optional[bool] = Field(None, description="Whether diet plan has been finalized")

