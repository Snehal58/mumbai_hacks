"""Nutrition-related tools."""

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from prompts.nutrition_agent_prompt import NUTRITION_AGENT_PROMPT
from services.nutrition_service import NutritionService
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
    template = ChatPromptTemplate.from_messages([
        ("system", NUTRITION_AGENT_PROMPT.template),
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

