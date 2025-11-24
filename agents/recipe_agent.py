"""Recipe Finder Agent."""

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from typing import List, Dict, Any, Optional
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from services.edamam_service import EdamamService
from services.spoonacular_service import SpoonacularService
from models.schemas import Recipe, NutritionGoal, MealContext
from utils.logger import setup_logger

logger = setup_logger(__name__)

llm = ChatOpenAI(
    model=AGENT_CONFIG["recipe_agent"]["model"],
    temperature=AGENT_CONFIG["recipe_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

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
        nutrition_goals: Dictionary with nutrition requirements
        meal_context: Dictionary with meal context (type, cuisine, etc.)
        max_results: Maximum number of recipes to return
        
    Returns:
        List of recipe dictionaries
    """
    try:
        # Try Spoonacular first
        recipes = spoonacular_service.search_recipes(
            query=meal_context.get("query", ""),
            min_protein=nutrition_goals.get("protein"),
            max_calories=nutrition_goals.get("calories"),
            cuisine=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
            diet=meal_context.get("dietary_restrictions"),
            max_results=max_results
        )
        
        # Fallback to Edamam if needed
        if not recipes:
            recipes = edamam_service.search_recipes(
                query=meal_context.get("query", ""),
                min_protein=nutrition_goals.get("protein"),
                max_calories=nutrition_goals.get("calories"),
                cuisine_type=meal_context.get("cuisine_preference", [None])[0] if meal_context.get("cuisine_preference") else None,
                meal_type=meal_context.get("meal_type"),
                diet=meal_context.get("dietary_restrictions"),
                max_results=max_results
            )
        
        return recipes
    except Exception as e:
        logger.error(f"Error in recipe search: {e}")
        return []


async def find_recipes(
    nutrition_goals: Optional[NutritionGoal],
    meal_context: Optional[MealContext],
    max_results: int = 10
) -> List[Recipe]:
    """Main function to find recipes."""
    nutrition_dict = {}
    if nutrition_goals:
        nutrition_dict = nutrition_goals.dict(exclude_none=True)
    
    context_dict = {}
    if meal_context:
        context_dict = meal_context.dict(exclude_none=True)
    
    recipe_dicts = search_recipes.invoke({
        "nutrition_goals": nutrition_dict,
        "meal_context": context_dict,
        "max_results": max_results
    })
    
    recipes = []
    for recipe_dict in recipe_dicts:
        try:
            recipes.append(Recipe(**recipe_dict))
        except Exception as e:
            logger.warning(f"Error parsing recipe: {e}")
            continue
    
    return recipes

