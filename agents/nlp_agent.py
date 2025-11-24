"""Natural Language Understanding Agent."""

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.tools import tool
from typing import Dict, Any
from config.settings import settings
from config.agent_config import AGENT_CONFIG
from models.schemas import ParsedRequest, NutritionGoal, MealContext
import json

# Initialize LLM
llm = ChatOpenAI(
    model=AGENT_CONFIG["nlp_agent"]["model"],
    temperature=AGENT_CONFIG["nlp_agent"]["temperature"],
    api_key=settings.openai_api_key,
)


@tool
def parse_user_request(prompt: str) -> Dict[str, Any]:
    """Parse user's natural language request into structured format.
    
    Args:
        prompt: User's natural language prompt
        
    Returns:
        Dictionary with parsed information including nutrition goals, meal context, etc.
    """
    system_prompt = AGENT_CONFIG["nlp_agent"]["system_prompt"]
    
    template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """Parse this user request: {prompt}

Return valid JSON with the following structure:
{{
    "nutrition_goals": {{"calories": number, "protein": number, "carbs": number, "fats": number}},
    "meal_context": {{"meal_type": string, "location": string, "budget": number, "cuisine_preference": [string], "dietary_restrictions": [string]}},
    "intent": ["recipes", "restaurants", "products"]  // List based on what user wants
}}""")
    ])
    
    chain = template | llm
    response = chain.invoke({"prompt": prompt})
    
    # Extract JSON from response
    content = response.content
    try:
        # Try to extract JSON if wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(content)
        return parsed
    except json.JSONDecodeError:
        # Fallback: return basic structure with default intent
        return {
            "raw_prompt": prompt,
            "nutrition_goals": {},
            "meal_context": {},
            "intent": ["recipes", "restaurants"]  # Default to both
        }


async def parse_request(prompt: str, context: Dict[str, Any] = None) -> ParsedRequest:
    """Main function to parse user request."""
    if context is None:
        context = {}
    
    # Combine prompt with context
    full_prompt = prompt
    if context:
        full_prompt += f"\n\nAdditional context: {json.dumps(context)}"
    
    parsed_data = parse_user_request.invoke({"prompt": full_prompt})
    
    # Convert to ParsedRequest model
    nutrition_goals = None
    if parsed_data.get("nutrition_goals"):
        nutrition_goals = NutritionGoal(**parsed_data["nutrition_goals"])
    
    meal_context = None
    if parsed_data.get("meal_context"):
        meal_context = MealContext(**parsed_data["meal_context"])
    
    # Extract intent, default to both recipes and restaurants if not specified
    intent = parsed_data.get("intent", ["recipes", "restaurants"])
    if not isinstance(intent, list):
        intent = ["recipes", "restaurants"]  # Fallback to default
    
    return ParsedRequest(
        nutrition_goals=nutrition_goals,
        meal_context=meal_context,
        raw_prompt=prompt,
        intent=intent
    )

