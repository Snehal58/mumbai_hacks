"""Agent-specific configuration."""

from typing import Dict, Any

# Agent configuration for LangGraph Supervisor
AGENT_CONFIG: Dict[str, Any] = {
    "supervisor": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.3,
        "max_iterations": 3,
    },
    "nlp_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.2,
        "max_iterations": 3,
    },
    "recipe_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.5,
        "max_iterations": 3,
    },
    "restaurant_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.5,
        "max_iterations": 3,
    },
    "product_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.5,
        "max_iterations": 3,
    },
    "nutrition_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.1,
        "max_iterations": 3,
    },
    "planner_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.4,
        "max_iterations": 3,
    },
    "goal_journey_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.4,
        "max_iterations": 3,
    },
    "workout_agent": {
        "model": "gpt-4o-mini",
        "fallback_model": "claude-3-haiku-20240307",
        "temperature": 0.4,
        "max_iterations": 3,
    },
}
