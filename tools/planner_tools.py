"""Planner-related tools."""

from langchain.tools import tool
from typing import Dict, Any
import json
from utils.logger import setup_logger

logger = setup_logger(__name__)


@tool
def create_meal_plan_from_results(
    meals_per_day: int = 3,
    meal_items: str = "[]"
) -> str:
    """Create a comprehensive meal plan structure.
    
    IMPORTANT: You can generate meal items directly from the user's questionnaire data (goals, 
    preferences, dietary restrictions, nutrition needs) using your knowledge. You do NOT need to 
    use search_recipes, search_restaurants, or search_products unless the user specifically 
    requests recipes from a database, restaurant recommendations, or product recommendations.
    
    When you have the user's complete questionnaire data, generate appropriate meal items directly 
    with this structure for each item:
    {
        "name": "Meal name",
        "description": "Brief description",
        "nutrition": {
            "calories": 500.0,
            "protein": 30.0,
            "carbs": 60.0,
            "fats": 15.0
        }
    }
    
    Then pass the list of meal items as a JSON string to this tool.
    
    Args:
        meals_per_day: Number of meals per day (default: 3)
        meal_items: JSON string of meal items. Can be generated directly from user data OR 
                   found using search_recipes/search_restaurants/search_products tools (default: empty list)
        
    Returns:
        JSON string with the complete meal plan structure
    """
    try:
        # Parse meal items provided by the agent
        try:
            meal_items = json.loads(meal_items) if meal_items else []
        except:
            meal_items = []
        
        # Ensure meal_items is a list
        if not isinstance(meal_items, list):
            meal_items = []
        
        # Structure meals according to meals_per_day
        # If we have more items than meals_per_day, distribute them across meals
        # If we have fewer items, we'll structure them appropriately
        structured_meals = []
        
        # Define meal types based on meals_per_day
        meal_types = []
        if meals_per_day == 3:
            meal_types = ["Breakfast", "Lunch", "Dinner"]
        elif meals_per_day == 4:
            meal_types = ["Breakfast", "Lunch", "Snack", "Dinner"]
        elif meals_per_day == 5:
            meal_types = ["Breakfast", "Mid-Morning Snack", "Lunch", "Afternoon Snack", "Dinner"]
        elif meals_per_day == 6:
            meal_types = ["Breakfast", "Mid-Morning Snack", "Lunch", "Afternoon Snack", "Dinner", "Evening Snack"]
        else:
            # For other numbers, create generic meal names
            meal_types = [f"Meal {i+1}" for i in range(meals_per_day)]
        
        # Distribute meal items across the meal types
        for i, meal_type in enumerate(meal_types):
            meal_data = {
                "type": meal_type,
                "items": [],
                "nutrition": {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
            }
            
            # Distribute items evenly or assign based on index
            items_per_meal = len(meal_items) // meals_per_day
            remainder = len(meal_items) % meals_per_day
            
            start_idx = i * items_per_meal + min(i, remainder)
            end_idx = start_idx + items_per_meal + (1 if i < remainder else 0)
            
            for item in meal_items[start_idx:end_idx]:
                meal_data["items"].append(item)
                nutrition = item.get("nutrition", {})
                for key in meal_data["nutrition"]:
                    meal_data["nutrition"][key] += nutrition.get(key, 0.0)
            
            structured_meals.append(meal_data)
        
        # Create meal plan structure
        meal_plan = {
            "meals_per_day": meals_per_day,
            "meals": structured_meals,
            "total_nutrition": {},
            "recommendations": []
        }
        
        # Calculate total nutrition
        total_nutrition = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
        for meal in structured_meals:
            nutrition = meal.get("nutrition", {})
            for key in total_nutrition:
                total_nutrition[key] += nutrition.get(key, 0.0)
        
        meal_plan["total_nutrition"] = total_nutrition
        meal_plan["is_saved"] = True
        
        return json.dumps(meal_plan, indent=2)
    except Exception as e:
        logger.error(f"Error creating meal plan: {e}")
        return json.dumps({"error": str(e), "meals": []})

