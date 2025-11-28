"""Diet collection schema."""

from pydantic import BaseModel, Field


class MealNutrient(BaseModel):
    """Nested model for meal nutrient in diet collection."""
    name: str = Field(..., description="Nutrient name")
    qty: float = Field(..., description="Quantity of the nutrient")
    unit: str = Field(..., description="Unit of measurement")


class DietCollection(BaseModel):
    """Diet collection model."""
    user_id: str = Field(..., description="User identifier")
    meal_no: int = Field(..., description="Meal number")
    meal_time: str = Field(..., description="Time of the meal")
    meal_description: str = Field(..., description="Description of the meal")
    meal_nutrient: MealNutrient = Field(..., description="Nutrient information with name, qty, and unit")

