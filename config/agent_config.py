"""Agent-specific configuration."""

from typing import Dict, Any

# Agent configuration for LangGraph Supervisor
AGENT_CONFIG: Dict[str, Any] = {
    "supervisor": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.3,
        "max_iterations": 20,
    },
    "nlp_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.2,
        "max_iterations": 20,
    },
    "recipe_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.5,
        "max_iterations": 20,
    },
    "restaurant_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.5,
        "max_iterations": 20,
    },
    "product_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.5,
        "max_iterations": 20,
    },
    "nutrition_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.1,
        "max_iterations": 20,
    },
    "planner_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.4,
        "max_iterations": 20,
    },
}
