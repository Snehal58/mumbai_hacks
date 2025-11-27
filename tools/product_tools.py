"""Product-related tools."""

import asyncio
from langchain.tools import tool
from typing import List, Dict, Any, Optional
from services.perplexity_service import PerplexityService
from utils.logger import setup_logger

logger = setup_logger(__name__)

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
def search_products(
    nutrition_goals: Dict[str, Any],
    product_type: str = "protein powder",
    max_results: int = 5,
    location: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search for nutrition products (supplements, packaged foods) using Perplexity API.
    Searches for products on Swiggy and Zomato and includes links when available.
    
    Args:
        nutrition_goals: Dictionary with nutrition requirements (calories, protein, carbs, fats)
        product_type: Type of product to search for (e.g., "protein powder", "supplements", "nutrition bars", "food items")
        max_results: Maximum number of products to return
        location: Optional location for local search (e.g., "Bangalore", "Mumbai")
        
    Returns:
        List of product dictionaries with name, brand, nutrition, price, swiggy_link, zomato_link, etc.
    """
    try:
        logger.info(f"Searching for {product_type} products using Perplexity")
        
        # Use Perplexity to search for products
        products = _run_async(
            perplexity_service.search_products(
                product_type=product_type,
                nutrition_goals=nutrition_goals,
                location=location,
                max_results=max_results
            )
        )
        
        # Ensure all products have required fields
        for product in products:
            if "nutrition" not in product:
                product["nutrition"] = {
                    "calories": 0.0,
                    "protein": 0.0,
                    "carbs": 0.0,
                    "fats": 0.0,
                }
            if "swiggy_link" not in product:
                product["swiggy_link"] = None
            if "zomato_link" not in product:
                product["zomato_link"] = None
            if "links" not in product:
                # Initialize links array if not present
                product["links"] = []
                # Add existing swiggy/zomato links to the links array
                if product.get("swiggy_link"):
                    product["links"].append({
                        "type": "swiggy",
                        "url": product["swiggy_link"]
                    })
                if product.get("zomato_link"):
                    product["links"].append({
                        "type": "zomato",
                        "url": product["zomato_link"]
                    })
            # Ensure links array has max 5 items
            if len(product.get("links", [])) > 5:
                product["links"] = product["links"][:5]
            if "purchase_url" not in product:
                # Use first link from links array, or Swiggy or Zomato link as purchase URL if available
                if product.get("links") and len(product["links"]) > 0:
                    product["purchase_url"] = product["links"][0]["url"]
                else:
                    product["purchase_url"] = product.get("swiggy_link") or product.get("zomato_link")
        
        logger.info(f"Found {len(products)} products")
        return products
        
    except Exception as e:
        logger.error(f"Error searching for products: {e}", exc_info=True)
        # Return empty list on error
        return []

