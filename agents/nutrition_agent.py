"""Nutrition Analysis Agent."""

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.tools import tool
from typing import Dict, Any, List
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from services.nutrition_service import NutritionService
from models.schemas import NutritionGoal
from utils.logger import setup_logger

logger = setup_logger(__name__)

llm = ChatOpenAI(
    model=AGENT_CONFIG["nutrition_agent"]["model"],
    temperature=AGENT_CONFIG["nutrition_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

nutrition_service = NutritionService()


@tool
def analyze_nutrition(
    meal_nutrition: Dict[str, float],
    goals: Dict[str, float]
) -> Dict[str, Any]:
    """Analyze if meal meets nutrition goals.
    
    Args:
        meal_nutrition: Dictionary with meal nutrition values
        goals: Dictionary with nutrition goals
        
    Returns:
        Dictionary with analysis results
    """
    validation = nutrition_service.validate_nutrition_goals(meal_nutrition, goals)
    
    # Calculate gaps
    gaps = {}
    for key, goal_value in goals.items():
        if key in meal_nutrition:
            gap = goal_value - meal_nutrition[key]
            gaps[key] = gap if gap > 0 else 0
    
    # Use LLM to provide recommendations
    system_prompt = AGENT_CONFIG["nutrition_agent"]["system_prompt"]
    
    template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """Analyze this meal plan:
        
        Meal Nutrition: {meal_nutrition}
        Goals: {goals}
        Gaps: {gaps}
        
        Provide recommendations to meet the goals.""")
    ])
    
    chain = template | llm
    response = chain.invoke({
        "meal_nutrition": meal_nutrition,
        "goals": goals,
        "gaps": gaps
    })
    
    return {
        "validation": validation,
        "gaps": gaps,
        "recommendations": response.content,
        "meets_goals": all(validation.values()) if validation else False
    }


async def analyze_meal_plan(
    meals: List[Dict[str, Any]],
    goals: NutritionGoal
) -> Dict[str, Any]:
    """Analyze a complete meal plan against nutrition goals."""
    # Calculate total nutrition
    total_nutrition = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fats": 0.0,
    }
    
    for meal in meals:
        nutrition = meal.get("nutrition", {})
        for key in total_nutrition:
            total_nutrition[key] += nutrition.get(key, 0.0)
    
    goals_dict = goals.dict(exclude_none=True)
    
    analysis = analyze_nutrition.invoke({
        "meal_nutrition": total_nutrition,
        "goals": goals_dict
    })
    
    return {
        "total_nutrition": total_nutrition,
        **analysis
    }

