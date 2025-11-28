"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


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


class PlannerRequest(BaseModel):
    """Request model for planner agent endpoint."""
    prompt: str = Field(..., description="User's prompt describing diet plan requirements")
    session_id: Optional[str] = Field(None, description="Session identifier for context continuity")


class RestaurantRequest(BaseModel):
    """Request model for restaurant agent endpoint."""
    prompt: Optional[str] = Field(None, description="User's prompt describing restaurant search")
    session_id: Optional[str] = Field(None, description="Session identifier for context continuity")
    location: Optional[str] = Field(None, description="Location for restaurant search")
    cuisine_type: Optional[str] = Field(None, description="Preferred cuisine type")
    budget: Optional[float] = Field(None, description="Budget constraint")
    max_distance: Optional[float] = Field(None, description="Maximum distance in km")
    search_query: Optional[str] = Field(None, description="Search query for restaurants")


class ProductRequest(BaseModel):
    """Request model for product agent endpoint."""
    prompt: Optional[str] = Field(None, description="User's prompt describing product search")
    session_id: Optional[str] = Field(None, description="Session identifier for context continuity")
    search_query: Optional[str] = Field(None, description="Search query for products")
    nutrition_requirements: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Nutrition requirements (calories, protein, etc.)"
    )
    budget: Optional[float] = Field(None, description="Budget constraint")


class RecipeRequest(BaseModel):
    """Request model for recipe search endpoint."""
    prompt: Optional[str] = Field(None, description="User's prompt describing recipe search")
    session_id: Optional[str] = Field(None, description="Session identifier for context continuity")
    search_query: Optional[str] = Field(None, description="Search query for recipes (e.g., 'chicken curry', 'vegetarian pasta')")
    cuisine_type: Optional[str] = Field(None, description="Preferred cuisine type")
    diet: Optional[List[str]] = Field(None, description="Dietary restrictions (e.g., 'vegetarian', 'vegan', 'gluten-free')")
    nutrition_requirements: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Nutrition requirements (calories, protein, carbs, fats, etc.)"
    )
    max_results: Optional[int] = Field(5, description="Maximum number of recipes to return")


class SSEEvent(BaseModel):
    """SSE event model for streaming responses."""
    event: str = Field(..., description="Event type: log, thinking, tool_call, response, done, error")
    data: Dict[str, Any] = Field(..., description="Event data")
    id: Optional[str] = Field(None, description="Event ID for reconnection")


class MealConsumption(BaseModel):
    """Model for a single meal consumption."""
    meal_type: str = Field(..., description="Meal type: breakfast, lunch, dinner, snack")
    planned_nutrition: Dict[str, float] = Field(..., description="Planned nutrition values (calories, protein, etc.)")
    actual_nutrition: Dict[str, float] = Field(..., description="Actual nutrition values consumed")


class GoalImpactRequest(BaseModel):
    """Request model for goal impact analysis."""
    daily_goal: NutritionGoal = Field(..., description="Daily nutrition goal")
    meals_per_day: int = Field(..., description="Number of meals per day")
    consumed_meals: List[MealConsumption] = Field(..., description="List of meals consumed (planned vs actual)")
    remaining_meals: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="Remaining planned meals for the day (optional)"
    )


class GoalImpactResponse(BaseModel):
    """Response model for goal impact analysis."""
    impact_analysis: Dict[str, Any] = Field(..., description="Detailed impact analysis")
    current_status: Dict[str, Any] = Field(..., description="Current status vs goal")
    suggestions: List[str] = Field(..., description="Suggestions to get back on track")
    adjusted_plan: Optional[Dict[str, Any]] = Field(None, description="Adjusted meal plan for remaining meals")
    severity: str = Field(..., description="Impact severity: low, medium, high")


class MealNutritionRequest(BaseModel):
    """Request model for meal nutrition lookup."""
    meal_description: str = Field(..., description="Description of the meal (e.g., 'pavbhaji', '1 bowl of oatmeal', '2 slices of pizza')")
    serving_size: Optional[str] = Field(None, description="Optional serving size specification (e.g., '1 bowl', '2 pieces', 'medium portion')")
    cuisine_type: Optional[str] = Field(None, description="Optional cuisine type (e.g., 'Indian', 'Italian', 'Chinese')")


class MealNutritionResponse(BaseModel):
    """Response model for meal nutrition lookup."""
    meal_name: str = Field(..., description="Identified meal name")
    serving_size: Optional[str] = Field(None, description="Serving size if specified")
    nutrition: Dict[str, float] = Field(..., description="Nutrition values (calories, protein, carbs, fats, fiber, etc.)")
    confidence: str = Field(..., description="Confidence level: high, medium, low")
    source: Optional[str] = Field(None, description="Source of nutrition data")
    notes: Optional[str] = Field(None, description="Additional notes about the nutrition data")


# Enums for collection fields
class GoalType(str, Enum):
    """User goal type enum."""
    MUSCLE_GAIN = "muscle gain"
    FAT_LOSS = "fat loss"


class WorkoutType(str, Enum):
    """Workout type enum."""
    UPPER = "upper"
    LOWER = "lower"
    FULL_BODY = "full body"


# Collection Schemas
class User(BaseModel):
    """User collection model."""
    user_id: str = Field(..., description="Unique user identifier")
    weight: float = Field(..., description="User weight in kg")
    height: float = Field(..., description="User height in cm")
    BMI: float = Field(..., description="Body Mass Index")
    goal: GoalType = Field(..., description="User goal: muscle gain or fat loss")


class Workout(BaseModel):
    """Workout collection model."""
    user_id: str = Field(..., description="User identifier")
    date: datetime = Field(..., description="Workout date")
    type: WorkoutType = Field(..., description="Workout type: upper, lower, or full body")
    repetitions: int = Field(..., description="Number of repetitions")
    expiry: bool = Field(..., description="Whether the workout has expired")


class WorkoutLog(BaseModel):
    """Workout logs collection model."""
    user_id: str = Field(..., description="User identifier")
    date: datetime = Field(..., description="Workout log date")
    type: str = Field(..., description="Workout type")
    plan: str = Field(..., description="Workout plan")
    is_extra: bool = Field(..., description="Whether this is an extra workout")


class DietLog(BaseModel):
    """Diet logs collection model."""
    user_id: str = Field(..., description="User identifier")
    meal_name: str = Field(..., description="Name of the meal")
    date: datetime = Field(..., description="Date of the meal")
    meal_time: str = Field(..., description="Time of the meal")
    meal_description: str = Field(..., description="Description of the meal")
    meal_nutrients: Dict[str, float] = Field(..., description="Nutrition values of the meal")


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


class GoalCollection(BaseModel):
    """Goal collection model."""
    user_id: str = Field(..., description="User identifier")
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


