"""Recipe-related tools."""

import asyncio
from langchain.tools import tool
from typing import List, Dict, Any
from services.edamam_service import EdamamService
from services.spoonacular_service import SpoonacularService
from services.perplexity_service import PerplexityService
from utils.logger import setup_logger

logger = setup_logger(__name__)

edamam_service = EdamamService()
spoonacular_service = SpoonacularService()
perplexity_service = PerplexityService()


def _run_async(coro):
    """Helper to run async function synchronously."""
    try:
        # Check if we're in an async context
        asyncio.get_running_loop()
        # If we're here, we're in an async context
        # Use nest_asyncio if available, otherwise use thread executor
        try:
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
            return asyncio.run(coro)
        except ImportError:
            # Fallback: create a new event loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
    except RuntimeError:
        # No event loop running, create a new one
        return asyncio.run(coro)


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
            # Use Perplexity to find recipes
            recipes = await perplexity_service.search_recipes(
                query=meal_context.get("query", ""),
                min_protein=nutrition_goals.get("protein"),
                max_calories=nutrition_goals.get("calories"),
                cuisine=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
                diet=meal_context.get("dietary_restrictions"),
                meal_type=meal_context.get("meal_type"),
                max_results=max_results
            )
            
            # # Fallback to Spoonacular if Perplexity returns no results
            # if not recipes:
            #     logger.info("Perplexity returned no results, trying Spoonacular...")
            #     recipes = await spoonacular_service.search_recipes(
            #         query=meal_context.get("query", ""),
            #         min_protein=nutrition_goals.get("protein"),
            #         max_calories=nutrition_goals.get("calories"),
            #         cuisine=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
            #         diet=meal_context.get("dietary_restrictions"),
            #         max_results=max_results
            #     )
            
            # # Fallback to Edamam if still no results
            # if not recipes:
            #     logger.info("Spoonacular returned no results, trying Edamam...")
            #     recipes = await edamam_service.search_recipes(
            #         query=meal_context.get("query", ""),
            #         min_protein=nutrition_goals.get("protein"),
            #         max_calories=nutrition_goals.get("calories"),
            #         cuisine_type=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
            #         meal_type=meal_context.get("meal_type"),
            #         diet=meal_context.get("dietary_restrictions"),
            #         max_results=max_results
            #     )
            
            return recipes
        
        return _run_async(_search())
    except Exception as e:
        logger.error(f"Error in recipe search: {e}")
        return []

