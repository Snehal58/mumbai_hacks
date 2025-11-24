"""Product Finder Agent."""

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from typing import List, Dict, Any, Optional
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from models.schemas import Product, NutritionGoal
from utils.logger import setup_logger

logger = setup_logger(__name__)

llm = ChatOpenAI(
    model=AGENT_CONFIG["product_agent"]["model"],
    temperature=AGENT_CONFIG["product_agent"]["temperature"],
    api_key=settings.openai_api_key,
)


@tool
def search_products(
    nutrition_goals: Dict[str, Any],
    product_type: str = "protein powder",
    max_results: int = 5
) -> List[Dict[str, Any]]:
    """Search for nutrition products (supplements, packaged foods).
    
    Args:
        nutrition_goals: Dictionary with nutrition requirements
        product_type: Type of product to search for
        max_results: Maximum number of products to return
        
    Returns:
        List of product dictionaries
    """
    # This is a placeholder - in production, you'd integrate with:
    # - E-commerce APIs (Amazon, Flipkart, etc.)
    # - Nutrition product databases
    # - Supplement APIs
    
    logger.info(f"Searching for {product_type} products")
    
    # Mock data for demonstration
    products = []
    if "protein" in product_type.lower():
        products = [
            {
                "name": "Whey Protein Powder",
                "brand": "Brand X",
                "nutrition": {
                    "calories": 120.0,
                    "protein": 25.0,
                    "carbs": 3.0,
                    "fats": 1.0,
                },
                "price": 2000.0,
                "price_per_unit": "₹2000 for 1kg",
            },
            {
                "name": "Plant Protein Powder",
                "brand": "Brand Y",
                "nutrition": {
                    "calories": 110.0,
                    "protein": 22.0,
                    "carbs": 4.0,
                    "fats": 2.0,
                },
                "price": 1800.0,
                "price_per_unit": "₹1800 for 1kg",
            },
        ]
    
    return products[:max_results]


async def find_products(
    nutrition_goals: Optional[NutritionGoal],
    product_type: str = "protein powder",
    max_results: int = 5
) -> List[Product]:
    """Main function to find products."""
    nutrition_dict = {}
    if nutrition_goals:
        nutrition_dict = nutrition_goals.dict(exclude_none=True)
    
    product_dicts = search_products.invoke({
        "nutrition_goals": nutrition_dict,
        "product_type": product_type,
        "max_results": max_results
    })
    
    products = []
    for product_dict in product_dicts:
        try:
            products.append(Product(**product_dict))
        except Exception as e:
            logger.warning(f"Error parsing product: {e}")
            continue
    
    return products

