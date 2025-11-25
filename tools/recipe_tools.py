"""Recipe-related tools."""

import asyncio
from langchain.tools import tool
from typing import List, Dict, Any
from services.edamam_service import EdamamService
from services.spoonacular_service import SpoonacularService
from utils.logger import setup_logger

logger = setup_logger(__name__)

edamam_service = EdamamService()
spoonacular_service = SpoonacularService()


@tool
def search_recipes(
    nutrition_goals: Dict[str, Any],
    meal_context: Dict[str, Any],
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """Search for recipes matching nutrition goals and meal context.
    
    Args:
        nutrition_goals: Dictionary with nutrition requirements (calories, protein, carbs, fats)
        meal_context: Dictionary with meal context (meal_type, cuisine_preference, dietary_restrictions, query)
        max_results: Maximum number of recipes to return
        
    Returns:
        List of recipe dictionaries with id, title, ingredients, nutrition, etc.
    """
    try:
        async def _search():
            # Try Spoonacular first
            recipes = await spoonacular_service.search_recipes(
                query=meal_context.get("query", ""),
                min_protein=nutrition_goals.get("protein"),
                max_calories=nutrition_goals.get("calories"),
                cuisine=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
                diet=meal_context.get("dietary_restrictions"),
                max_results=max_results
            )
            
            # Fallback to Edamam if needed
            if not recipes:
                recipes = await edamam_service.search_recipes(
                    query=meal_context.get("query", ""),
                    min_protein=nutrition_goals.get("protein"),
                    max_calories=nutrition_goals.get("calories"),
                    cuisine_type=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
                    meal_type=meal_context.get("meal_type"),
                    diet=meal_context.get("dietary_restrictions"),
                    max_results=max_results
                )
            
            return recipes
        
        # Run async function synchronously
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, we need to use nest_asyncio or create a task
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(_search())
        except RuntimeError:
            # No event loop running, create a new one
            return asyncio.run(_search())
    except Exception as e:
        logger.error(f"Error in recipe search: {e}")
        return []

