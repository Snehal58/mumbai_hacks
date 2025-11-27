"""Planner-related tools."""

from langchain.tools import tool
from typing import Dict, Any
import json
from utils.logger import setup_logger

logger = setup_logger(__name__)


@tool
def create_meal_plan_from_results(
    recipes_data: str,
    restaurants_data: str = "",
    products_data: str = "",
    nutrition_goals: str = ""
) -> str:
    """Create a comprehensive meal plan from recipes, restaurants, and products.
    
    Args:
        recipes_data: JSON string or description of recipes found
        restaurants_data: JSON string or description of restaurants found
        products_data: JSON string or description of products found
        nutrition_goals: JSON string with nutrition goals (calories, protein, carbs, fats)
        
    Returns:
        JSON string with the complete meal plan
    """
    try:
        # Parse input data
        recipes = []
        if recipes_data:
            try:
                recipes = json.loads(recipes_data) if recipes_data.startswith("[") or recipes_data.startswith("{") else []
            except:
                recipes = []
        
        restaurant_meals = []
        if restaurants_data:
            try:
                restaurant_meals = json.loads(restaurants_data) if restaurants_data.startswith("[") or restaurants_data.startswith("{") else []
            except:
                restaurant_meals = []
        
        products = []
        if products_data:
            try:
                products = json.loads(products_data) if products_data.startswith("[") or products_data.startswith("{") else []
            except:
                products = []
        
        goals = {}
        if nutrition_goals:
            try:
                goals = json.loads(nutrition_goals) if nutrition_goals.startswith("{") else {}
            except:
                goals = {}
        
        # Combine into meal plan
        meal_items = []
        for recipe in recipes:
            if isinstance(recipe, dict):
                meal_items.append({
                    "type": "recipe",
                    "data": recipe,
                    "nutrition": recipe.get("nutrition", {})
                })
        
        for meal in restaurant_meals:
            if isinstance(meal, dict):
                meal_items.append({
                    "type": "restaurant",
                    "data": meal,
                    "nutrition": meal.get("estimated_nutrition", meal.get("nutrition", {}))
                })
        
        # Create meal plan structure
        meal_plan = {
            "meals": meal_items,
            "total_nutrition": {},
            "recommendations": []
        }
        
        # Calculate total nutrition
        total_nutrition = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
        for item in meal_items:
            nutrition = item.get("nutrition", {})
            for key in total_nutrition:
                total_nutrition[key] += nutrition.get(key, 0.0)
        
        meal_plan["total_nutrition"] = total_nutrition
        
        return json.dumps(meal_plan, indent=2)
    except Exception as e:
        logger.error(f"Error creating meal plan: {e}")
        return json.dumps({"error": str(e), "meals": []})

