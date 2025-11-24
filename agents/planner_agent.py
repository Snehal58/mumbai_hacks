"""Planning/Orchestration Agent."""

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from typing import Dict, Any, List
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from models.schemas import ParsedRequest, MealPlan, AgentOutput
from agents.recipe_agent import find_recipes
from agents.restaurant_agent import find_restaurant_meals
from agents.product_agent import find_products
from agents.nutrition_agent import analyze_meal_plan
from utils.logger import setup_logger

logger = setup_logger(__name__)

llm = ChatOpenAI(
    model=AGENT_CONFIG["planner_agent"]["model"],
    temperature=AGENT_CONFIG["planner_agent"]["temperature"],
    api_key=settings.openai_api_key,
)


async def create_meal_plan(
    parsed_request: ParsedRequest,
    recipes: List = None,
    restaurant_meals: List = None,
    products: List = None
) -> AgentOutput:
    """Create a comprehensive meal plan based on parsed request and agent results.
    
    Args:
        parsed_request: Parsed user request
        recipes: List of Recipe objects from recipe_agent (optional)
        restaurant_meals: List of RestaurantMeal objects from restaurant_agent (optional)
        products: List of Product objects from product_agent (optional)
    """
    system_prompt = AGENT_CONFIG["planner_agent"]["system_prompt"]
    
    # Use provided results, or fetch if not provided (backward compatibility)
    if recipes is None:
        recipes = []
        if parsed_request.nutrition_goals and parsed_request.meal_context:
            try:
                recipes = await find_recipes(
                    parsed_request.nutrition_goals,
                    parsed_request.meal_context,
                    max_results=5
                )
            except Exception as e:
                logger.error(f"Error finding recipes: {e}")
    
    if restaurant_meals is None:
        restaurant_meals = []
        if parsed_request.meal_context and parsed_request.meal_context.location:
            try:
                restaurant_meals = await find_restaurant_meals(
                    parsed_request.meal_context,
                    max_results=5
                )
            except Exception as e:
                logger.error(f"Error finding restaurant meals: {e}")
    
    if products is None:
        products = []
        if parsed_request.nutrition_goals:
            try:
                products = await find_products(
                    parsed_request.nutrition_goals,
                    product_type="protein supplement",
                    max_results=3
                )
            except Exception as e:
                logger.error(f"Error finding products: {e}")
    
    # Combine into meal plan
    meal_items = []
    for recipe in recipes:
        meal_items.append({
            "type": "recipe",
            "data": recipe.dict(),
            "nutrition": recipe.nutrition
        })
    
    for meal in restaurant_meals:
        meal_items.append({
            "type": "restaurant",
            "data": meal.dict(),
            "nutrition": meal.estimated_nutrition
        })
    
    # Analyze nutrition
    nutrition_summary = {}
    if parsed_request.nutrition_goals and meal_items:
        nutrition_summary = await analyze_meal_plan(
            meal_items,
            parsed_request.nutrition_goals
        )
    
    # Use LLM to create explanation and recommendations
    template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """Create a meal plan explanation for the user:
        
        Request: {request}
        Recipes found: {recipes_count}
        Restaurants found: {restaurants_count}
        Nutrition analysis: {nutrition_summary}
        
        Provide a clear, helpful explanation and recommendations.""")
    ])
    
    chain = template | llm
    explanation_response = chain.invoke({
        "request": parsed_request.raw_prompt,
        "recipes_count": len(recipes),
        "restaurants_count": len(restaurant_meals),
        "nutrition_summary": nutrition_summary
    })
    
    meal_plan = MealPlan(
        meals=meal_items,
        total_nutrition=nutrition_summary.get("total_nutrition", {}),
        recommendations=[explanation_response.content] if explanation_response.content else []
    )
    
    return AgentOutput(
        meal_plan=meal_plan,
        recipes=recipes if recipes else None,
        restaurant_meals=restaurant_meals if restaurant_meals else None,
        products=products if products else None,
        nutrition_summary=nutrition_summary,
        explanation=explanation_response.content
    )

