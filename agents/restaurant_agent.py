"""Restaurant Finder Agent."""

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from typing import List, Dict, Any, Optional
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from services.maps_service import MapsService
from services.nutrition_service import NutritionService
from models.schemas import RestaurantMeal, MealContext
from utils.logger import setup_logger

logger = setup_logger(__name__)

llm = ChatOpenAI(
    model=AGENT_CONFIG["restaurant_agent"]["model"],
    temperature=AGENT_CONFIG["restaurant_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

maps_service = MapsService()
nutrition_service = NutritionService()


@tool
def search_restaurants(
    location: str,
    cuisine_type: Optional[str] = None,
    budget: Optional[float] = None,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """Search for restaurants near a location.
    
    Args:
        location: Location string (city, address, etc.)
        cuisine_type: Preferred cuisine type
        budget: Budget constraint
        max_results: Maximum number of restaurants to return
        
    Returns:
        List of restaurant dictionaries
    """
    try:
        restaurants = maps_service.search_restaurants(
            location=location,
            cuisine_type=cuisine_type,
            max_results=max_results
        )
        
        # Filter by budget if provided
        if budget:
            # This would require menu price data - simplified for now
            pass
        
        return restaurants
    except Exception as e:
        logger.error(f"Error in restaurant search: {e}")
        return []


@tool
def estimate_meal_nutrition(dish_name: str, cuisine_type: Optional[str] = None) -> Dict[str, float]:
    """Estimate nutrition for a restaurant dish.
    
    Args:
        dish_name: Name of the dish
        cuisine_type: Type of cuisine
        
    Returns:
        Dictionary with estimated nutrition values
    """
    try:
        nutrition = nutrition_service.estimate_restaurant_meal_nutrition(
            dish_name=dish_name,
            cuisine_type=cuisine_type
        )
        return nutrition
    except Exception as e:
        logger.error(f"Error estimating nutrition: {e}")
        return {}


async def find_restaurant_meals(
    meal_context: Optional[MealContext],
    max_results: int = 10
) -> List[RestaurantMeal]:
    """Main function to find restaurant meals."""
    if not meal_context or not meal_context.location:
        return []
    
    context_dict = meal_context.dict(exclude_none=True)
    cuisine_type = None
    if meal_context.cuisine_preference:
        cuisine_type = meal_context.cuisine_preference[0]
    
    restaurants = search_restaurants.invoke({
        "location": meal_context.location,
        "cuisine_type": cuisine_type,
        "budget": meal_context.budget,
        "max_results": max_results
    })
    
    restaurant_meals = []
    for restaurant in restaurants:
        # For each restaurant, we'd need to get menu items
        # This is simplified - in production, you'd integrate with menu APIs
        dish_name = f"Popular dish at {restaurant['name']}"
        nutrition = estimate_meal_nutrition.invoke({
            "dish_name": dish_name,
            "cuisine_type": cuisine_type
        })
        
        try:
            restaurant_meals.append(RestaurantMeal(
                restaurant_name=restaurant.get("name", ""),
                dish_name=dish_name,
                estimated_nutrition=nutrition,
                price=meal_context.budget / 3 if meal_context.budget else 0,  # Simplified
                location=restaurant.get("address", meal_context.location),
                rating=restaurant.get("rating"),
                cuisine_type=cuisine_type
            ))
        except Exception as e:
            logger.warning(f"Error creating restaurant meal: {e}")
            continue
    
    return restaurant_meals

