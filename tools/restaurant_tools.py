"""Restaurant-related tools."""

import asyncio
from langchain.tools import tool
from typing import List, Dict, Any, Optional
from services.maps_service import MapsService
from services.nutrition_service import NutritionService
from utils.logger import setup_logger

logger = setup_logger(__name__)

maps_service = MapsService()
nutrition_service = NutritionService()


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
        budget: Budget constraint (optional)
        max_results: Maximum number of restaurants to return
        
    Returns:
        List of restaurant dictionaries with name, address, rating, etc.
    """
    try:
        restaurants = _run_async(
            maps_service.search_restaurants(
                location=location,
                cuisine_type=cuisine_type,
                max_results=max_results
            )
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
        Dictionary with estimated nutrition values (calories, protein, carbs, fats)
    """
    try:
        nutrition = _run_async(
            nutrition_service.estimate_restaurant_meal_nutrition(
                dish_name=dish_name,
                cuisine_type=cuisine_type
            )
        )
        return nutrition
    except Exception as e:
        logger.error(f"Error estimating nutrition: {e}")
        return {}

