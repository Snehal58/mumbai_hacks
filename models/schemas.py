"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class WebSocketMessage(BaseModel):
    """WebSocket message from client."""
    prompt: str = Field(..., description="User's natural language prompt")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context (location, budget, preferences, etc.)"
    )


class WebSocketResponse(BaseModel):
    """WebSocket response to client."""
    type: str = Field(..., description="Response type: thinking, finding_records, searching_more, output")
    content: Any = Field(..., description="Response content")
    session_id: Optional[str] = Field(None, description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.now)


class NutritionGoal(BaseModel):
    """Nutrition goals model."""
    calories: Optional[float] = None
    protein: Optional[float] = None  # in grams
    carbs: Optional[float] = None  # in grams
    fats: Optional[float] = None  # in grams
    fiber: Optional[float] = None  # in grams


class MealContext(BaseModel):
    """Meal context information."""
    meal_type: Optional[str] = None  # breakfast, lunch, dinner, snack
    location: Optional[str] = None
    budget: Optional[float] = None
    cuisine_preference: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    preferences: Optional[List[str]] = None


class ParsedRequest(BaseModel):
    """Parsed user request structure."""
    nutrition_goals: Optional[NutritionGoal] = None
    meal_context: Optional[MealContext] = None
    raw_prompt: str
    intent: Optional[List[str]] = Field(
        default_factory=list,
        description="User intent: list of 'recipes', 'restaurants', 'products', or 'all'"
    )


class Recipe(BaseModel):
    """Recipe model."""
    id: str
    title: str
    description: Optional[str] = None
    ingredients: List[str]
    instructions: Optional[List[str]] = None
    nutrition: Dict[str, float]
    prep_time: Optional[int] = None  # in minutes
    cook_time: Optional[int] = None  # in minutes
    servings: Optional[int] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None


class RestaurantMeal(BaseModel):
    """Restaurant meal model."""
    restaurant_name: str
    dish_name: str
    description: Optional[str] = None
    estimated_nutrition: Dict[str, float]
    price: float
    location: str
    rating: Optional[float] = None
    cuisine_type: Optional[str] = None


class Product(BaseModel):
    """Product model."""
    name: str
    brand: Optional[str] = None
    nutrition: Dict[str, float]
    price: Optional[float] = None
    price_per_unit: Optional[str] = None
    image_url: Optional[str] = None
    purchase_url: Optional[str] = None


class MealPlan(BaseModel):
    """Complete meal plan model."""
    date: Optional[str] = None
    meals: List[Dict[str, Any]]  # List of meal items (recipes, restaurant meals, products)
    total_nutrition: Dict[str, float]
    total_cost: Optional[float] = None
    recommendations: Optional[List[str]] = None


class AgentOutput(BaseModel):
    """Final agent output."""
    meal_plan: Optional[MealPlan] = None
    recipes: Optional[List[Recipe]] = None
    restaurant_meals: Optional[List[RestaurantMeal]] = None
    products: Optional[List[Product]] = None
    nutrition_summary: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None

