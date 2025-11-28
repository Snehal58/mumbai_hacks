"""Collection schemas organized by collection type."""

from models.schemas import GoalType, WorkoutType
from models.schemas import User
from models.schemas import Workout
from models.schemas import WorkoutLog
from models.schemas import DietLog
from models.schemas import MealNutrient, DietCollection
from models.schemas import GoalCollection
from models.schemas import WebSocketMessage, WebSocketResponse
from models.schemas import (
    PlannerRequest,
    RestaurantRequest,
    ProductRequest,
    RecipeRequest,
    GoalImpactRequest,
    GoalImpactResponse,
    MealNutritionRequest,
    MealNutritionResponse,
)

__all__ = [
    "GoalType",
    "WorkoutType",
    "User",
    "Workout",
    "WorkoutLog",
    "DietLog",
    "MealNutrient",
    "DietCollection",
    "GoalCollection",
    "WebSocketMessage",
    "WebSocketResponse",
    "PlannerRequest",
    "RestaurantRequest",
    "ProductRequest",
    "RecipeRequest",
    "GoalImpactRequest",
    "GoalImpactResponse",
    "MealNutritionRequest",
    "MealNutritionResponse",
]

