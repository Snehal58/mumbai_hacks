"""Collection schemas organized by collection type."""

from models.schemas.enums import GoalType, WorkoutType
from models.schemas.user import User
from models.schemas.workout import Workout
from models.schemas.workout_log import WorkoutLog
from models.schemas.diet_log import DietLog
from models.schemas.diet_collection import MealNutrient, DietCollection
from models.schemas.goal_collection import GoalCollection
from models.schemas.websocket import WebSocketMessage, WebSocketResponse
from models.schemas.api import (
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

