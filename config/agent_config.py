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
        "system_prompt": """You are a Natural Language Understanding agent specialized in parsing 
        user meal planning requests. Extract key information including:
        - Nutrition goals (calories, protein, carbs, fats)
        - Meal context (breakfast, lunch, dinner, snacks)
        - Location
        - Budget
        - Dietary preferences and restrictions
        - Cuisine preferences
        - Intent: Determine what the user wants. Return a list containing one or more of:
          * "recipes" - if user wants recipe suggestions
          * "restaurants" - if user wants restaurant recommendations
          * "products" - if user wants product/supplement suggestions
          * If user wants everything or doesn't specify, return ["recipes", "restaurants"]
        
        Return structured JSON with all extracted information. The intent field should be a list of strings."""
    },
    "recipe_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.5,
        "max_results": 10,
    },
    "restaurant_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.5,
        "max_results": 10,
    },
    "product_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.5,
        "max_results": 5,
    },
    "nutrition_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.1,
        "system_prompt": """You are a Nutrition Analysis agent. Analyze meal plans and recipes 
        to ensure they meet nutritional requirements. Calculate totals, identify gaps, and 
        suggest adjustments."""
    },
    "planner_agent": {
        "model": "gpt-4-turbo-preview",
        "temperature": 0.4,
        "system_prompt": """You are a Meal Planning Orchestrator. Coordinate between different 
        agents to create comprehensive meal plans that meet user requirements. Optimize for 
        nutrition goals, budget constraints, and user preferences."""
    },
}

# Agent routing configuration for supervisor
AGENT_ROUTING = {
    "nlp_agent": "Natural Language Understanding",
    "recipe_agent": "Recipe Finding",
    "restaurant_agent": "Restaurant Finding",
    "product_agent": "Product Finding",
    "nutrition_agent": "Nutrition Analysis",
    "planner_agent": "Meal Planning",
}

