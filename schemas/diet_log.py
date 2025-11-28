"""Diet logs collection schema."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict


class DietLog(BaseModel):
    """Diet logs collection model."""
    user_id: str = Field(..., description="User identifier")
    meal_name: str = Field(..., description="Name of the meal")
    date: datetime = Field(..., description="Date of the meal")
    meal_time: str = Field(..., description="Time of the meal")
    meal_description: str = Field(..., description="Description of the meal")
    meal_nutrients: Dict[str, float] = Field(..., description="Nutrition values of the meal")

