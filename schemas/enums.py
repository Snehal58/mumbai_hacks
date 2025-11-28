"""Enums for collection fields."""

from enum import Enum


class GoalType(str, Enum):
    """User goal type enum."""
    MUSCLE_GAIN = "muscle gain"
    FAT_LOSS = "fat loss"


class WorkoutType(str, Enum):
    """Workout type enum."""
    UPPER = "upper"
    LOWER = "lower"
    FULL_BODY = "full body"

