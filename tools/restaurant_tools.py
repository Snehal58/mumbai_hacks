"""Restaurant-related tools."""

import asyncio
from langchain.tools import tool
from typing import List, Dict, Any, Optional
from services.maps_service import MapsService
from services.nutrition_service import NutritionService
from services.perplexity_service import PerplexityService
from utils.logger import setup_logger

logger = setup_logger(__name__)

maps_service = MapsService()
nutrition_service = NutritionService()
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


@tool
def search_restaurant_order_links(
    dish_name: str,
    location: str,
    platforms: Optional[List[str]] = None,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """Search for direct order links from Swiggy or Zomato for a specific dish at restaurants in a location.
    
    Use this tool when users ask for direct buy links, order links, or purchase links from food delivery platforms.
    
    Args:
        dish_name: Name of the dish (e.g., "paneer tikka", "butter chicken")
        location: Location string (e.g., "Kharadi, Pune", "Mumbai")
        platforms: List of platforms to search (e.g., ["swiggy", "zomato"]). Defaults to both if not specified.
        max_results: Maximum number of restaurants to return
        
    Returns:
        List of restaurant dictionaries with restaurant_name, dish_name, order_link (direct URL), rating, price, address, and platform
    """
    try:
        logger.info(f"Searching order links for {dish_name} in {location} on {platforms or ['swiggy', 'zomato']}")
        restaurants = _run_async(
            perplexity_service.search_restaurant_order_links(
                dish_name=dish_name,
                location=location,
                platforms=platforms,
                max_results=max_results
            )
        )
        logger.info(f"Found {len(restaurants)} restaurants with order links")
        if restaurants:
            logger.debug(f"Sample restaurant: {restaurants[0] if restaurants else 'None'}")
        return restaurants
    except Exception as e:
        logger.error(f"Error searching restaurant order links: {e}", exc_info=True)
        return []

