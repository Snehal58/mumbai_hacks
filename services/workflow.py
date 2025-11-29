"""Workflow for all agents and supervisor."""

from typing import Any, Dict, List
from datetime import datetime
from langgraph_supervisor import create_supervisor
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from tools.recipe_tools import search_recipes
from tools.restaurant_tools import search_restaurants, estimate_meal_nutrition
from tools.product_tools import search_products
from tools.planner_tools import create_meal_plan_from_results
from tools.goal_tools import get_active_user_goal, upsert_goal
from prompts.recipe_agent_prompt import RECIPE_AGENT_PROMPT
from prompts.restaurant_agent_prompt import RESTAURANT_AGENT_PROMPT
from prompts.product_agent_prompt import PRODUCT_AGENT_PROMPT
from prompts.planner_agent_prompt import PLANNER_AGENT_PROMPT
from prompts.goal_journey_agent_prompt import GOAL_JOURNEY_AGENT_PROMPT
from prompts.supervisor_prompt import SUPERVISOR_PROMPT
from utils.logger import setup_logger
from services.checkpoint import checkpoint_manager
from services.llm_factory import get_llm
from services.stream_agent import stream_agent_service
from models.database import get_database, get_diet_collection
from schemas.diet_collection import DietCollection, MealNutrient
import json
import uuid
import asyncio

# Try to import Anthropic exceptions for better error handling
try:
    import anthropic
    AnthropicError = getattr(anthropic, 'APIError', Exception)
    InternalServerError = getattr(anthropic, 'InternalServerError', Exception)
    RateLimitError = getattr(anthropic, 'RateLimitError', Exception)
    AuthenticationError = getattr(anthropic, 'AuthenticationError', Exception)
except ImportError:
    # Fallback if anthropic module is not available
    AnthropicError = Exception
    InternalServerError = Exception
    RateLimitError = Exception
    AuthenticationError = Exception

logger = setup_logger(__name__)

PLANNER_PREFERENCE_QUESTIONS = [
    {
        "key": "diet_type",
        "label": "Diet preference",
        "question": "Do you prefer vegetarian, non-vegetarian, vegan, or another diet style?",
    },
    {
        "key": "meals_per_day",
        "label": "Meals per day",
        "question": "How many meals or eating occasions would you like each day?",
    },
    {
        "key": "calorie_target",
        "label": "Calorie target",
        "question": "Do you have a daily calorie target or range I should aim for?",
    },
    {
        "key": "allergies",
        "label": "Allergies & restrictions",
        "question": "Are there any allergies, foods, or ingredients you want to avoid?",
    },
]


def _get_user_friendly_error_message(error: Exception) -> str:
    """Convert API errors to user-friendly messages."""
    error_str = str(error)
    error_type = type(error).__name__
    
    # Check for HTML error pages (Cloudflare/API errors) first
    if "<!DOCTYPE html>" in error_str or "Internal server error" in error_str or "500: Internal server error" in error_str:
        return "The AI service is temporarily unavailable. Please try again in a few moments."
    
    # Check if it's an Anthropic API error by type
    if isinstance(error, InternalServerError) or "InternalServerError" in error_type:
        return "The AI service is temporarily unavailable. Please try again in a few moments."
    elif isinstance(error, RateLimitError) or "RateLimitError" in error_type:
        return "Too many requests. Please wait a moment and try again."
    elif isinstance(error, AuthenticationError) or "AuthenticationError" in error_type:
        return "Authentication error. Please contact support."
    elif isinstance(error, AnthropicError) or "APIError" in error_type:
        return "An error occurred with the AI service. Please try again."
    elif isinstance(error, asyncio.TimeoutError):
        return "The request took too long. Please try again."
    else:
        # For other errors, provide a generic message
        return "An unexpected error occurred. Please try again."


def _get_next_planner_question(questionnaire: dict | None) -> dict | None:
    questionnaire = questionnaire or {}
    for question in PLANNER_PREFERENCE_QUESTIONS:
        key = question["key"]
        if not questionnaire.get(key):
            return question
    return None


def _format_questionnaire_summary(questionnaire: dict | None) -> str:
    if not questionnaire:
        return ""
    lines = []
    for question in PLANNER_PREFERENCE_QUESTIONS:
        key = question["key"]
        if key in questionnaire and questionnaire[key]:
            lines.append(f"- {question['label']}: {questionnaire[key]}")
    return "\n".join(lines)


def _convert_meal_plan_to_diet_collection(user_id: str, meal_plan: dict) -> List[Dict]:
    """Convert meal plan structure to DietCollection format.
    
    Creates a separate entry for each meal item in the diet collection.
    
    Args:
        user_id: User identifier
        meal_plan: Meal plan dictionary with 'meals' array
        
    Returns:
        List of DietCollection dictionaries ready for database insertion
    """
    diet_collections = []
    meals = meal_plan.get("meals", [])
    meal_item_counter = 1  # Counter for unique meal_no across all items
    
    for meal in meals:
        meal_type = meal.get("type", "Meal")
        meal_items = meal.get("items", [])
        
        # Create a separate entry for each meal item
        for item in meal_items:
            item_name = item.get("name", "Unknown item")
            item_desc = item.get("description", "")
            
            # Create meal description from item name and description
            if item_desc:
                meal_description = f"{item_name}: {item_desc}"
            else:
                meal_description = item_name
            
            # Get nutrition info for this item
            item_nutrition = item.get("nutrition", {})
            calories = item_nutrition.get("calories", 0.0)
            
            # Create DietCollection entry for this meal item
            diet_entry = {
                "user_id": user_id,
                "meal_no": meal_item_counter,
                "meal_time": meal_type,
                "meal_description": meal_description,
                "meal_nutrient": {
                    "name": "calories",
                    "qty": float(calories),
                    "unit": "kcal"
                }
            }
            
            diet_collections.append(diet_entry)
            meal_item_counter += 1
    
    return diet_collections


def _extract_single_question(content: str) -> str:
    """Extract only the first question from content that may contain multiple questions.
    
    Args:
        content: Response content that may contain multiple questions
        
    Returns:
        Content with only the first question
    """
    import re
    
    # Count question marks
    question_count = content.count('?')
    
    # If only one question mark, return as is
    if question_count <= 1:
        return content
    
    # If multiple questions, extract only the first one
    # Look for patterns like "1.", "2.", numbered lists, or multiple question marks
    lines = content.split('\n')
    first_question_lines = []
    found_first_question = False
    
    for line in lines:
        # Check if this line starts a numbered question (1., 2., etc.)
        if re.match(r'^\s*\d+[\.\)]\s+', line):
            if found_first_question:
                # We've already found the first question, stop here
                break
            found_first_question = True
            # Remove the number prefix
            line = re.sub(r'^\s*\d+[\.\)]\s+', '', line)
            first_question_lines.append(line)
        elif '?' in line:
            if found_first_question:
                # We've found the first question mark, stop at the next question
                break
            found_first_question = True
            first_question_lines.append(line)
        elif not found_first_question:
            # Before finding the first question, include all lines
            first_question_lines.append(line)
        else:
            # After finding the first question, stop if we see another question indicator
            if any(indicator in line.lower() for indicator in ['question', 'also', 'next', 'another']):
                break
            # Include lines that are part of the first question (continuation)
            if line.strip() and not re.match(r'^\s*\d+[\.\)]', line):
                first_question_lines.append(line)
    
    result = '\n'.join(first_question_lines).strip()
    
    # If we still have multiple question marks, take everything up to the second one
    if result.count('?') > 1:
        first_q_index = result.find('?')
        second_q_index = result.find('?', first_q_index + 1)
        if second_q_index > 0:
            result = result[:second_q_index + 1]
    
    # Clean up: remove any trailing "Please answer..." or similar phrases
    result = re.sub(r'\s*Please\s+(provide|answer|tell|let).*$', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\s*I\'d\s+like\s+to\s+(gather|ask).*$', '', result, flags=re.IGNORECASE)
    
    return result.strip()


def format_restaurant_output(content: Any) -> Dict[str, Any]:
    restaurants: List[Dict[str, Any]] = []
    parsed_content = content
    if isinstance(content, str):
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            parsed_content = {}
    if isinstance(parsed_content, dict):
        if "restaurants" in parsed_content:
            restaurants = parsed_content["restaurants"]
        elif "restaurant_meals" in parsed_content:
            restaurants = parsed_content["restaurant_meals"]
        elif isinstance(parsed_content.get("content"), dict):
            return format_restaurant_output(parsed_content["content"])
        elif isinstance(parsed_content.get("content"), list):
            restaurants = parsed_content["content"]
    elif isinstance(parsed_content, list):
        restaurants = parsed_content
    return {"restaurants": restaurants}


def format_product_output(content: Any) -> Dict[str, Any]:
    products: List[Dict[str, Any]] = []
    parsed_content = content
    if isinstance(content, str):
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            parsed_content = {}
    if isinstance(parsed_content, dict):
        if "products" in parsed_content:
            products = parsed_content["products"]
        elif "online_food" in parsed_content:
            products = parsed_content["online_food"]
        elif isinstance(parsed_content.get("content"), dict):
            return format_product_output(parsed_content["content"])
        elif isinstance(parsed_content.get("content"), list):
            products = parsed_content["content"]
    elif isinstance(parsed_content, list):
        products = parsed_content
    return {"products": products}


# ============================================================================
# Agent LLM Initializations
# ============================================================================

recipe_llm = get_llm("recipe_agent")

restaurant_llm = get_llm("restaurant_agent")

product_llm = get_llm("product_agent")

planner_llm = get_llm("planner_agent")

goal_journey_llm = get_llm("goal_journey_agent")

supervisor_llm = get_llm("supervisor")


# ============================================================================
# Agent Declarations
# ============================================================================

# Recipe Agent
recipe_agent = create_react_agent(
    model=recipe_llm,
    tools=[search_recipes,],
    name="recipe_agent",
    prompt=RECIPE_AGENT_PROMPT.template,
)


# Restaurant Agent
restaurant_agent = create_react_agent(
    model=restaurant_llm,
    tools=[search_restaurants, estimate_meal_nutrition],
    name="restaurant_agent",
    prompt=RESTAURANT_AGENT_PROMPT.template,
)


# Product Agent
product_agent = create_react_agent(
    model=product_llm,
    tools=[search_products],
    name="product_agent",
    prompt=PRODUCT_AGENT_PROMPT.template,
)


# Planner Agent
planner_agent = create_react_agent(
    model=planner_llm,
    tools=[create_meal_plan_from_results, search_recipes, search_restaurants, search_products],
    name="planner_agent",
    prompt=PLANNER_AGENT_PROMPT.template,
)


# Goal Journey Agent
goal_journey_agent = create_react_agent(
    model=goal_journey_llm,
    tools=[get_active_user_goal, upsert_goal],
    name="goal_journey_agent",
    prompt=GOAL_JOURNEY_AGENT_PROMPT.template,
)


# ============================================================================
# Supervisor Workflow
# ============================================================================

_supervisor_graph = None


def create_supervisor_graph():
    """Create the LangGraph supervisor graph using langgraph-supervisor."""
    
    agents = [
        recipe_agent,
        restaurant_agent,
        product_agent,
        planner_agent,
    ]
    
    workflow = create_supervisor(
        agents,
        model=supervisor_llm,
        prompt=SUPERVISOR_PROMPT.template,
    )
    
    return workflow.compile()


def get_supervisor_graph():
    """Get or create the supervisor graph instance (lazy initialization)."""
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = create_supervisor_graph()
    return _supervisor_graph


async def stream_supervisor(prompt: str, session_id: str = None):
    """Stream supervisor execution with real-time logs.
    
    Args:
        prompt: User's natural language prompt
        session_id: Session identifier for context continuity
        
    Yields:
        Dictionary events with type and data for SSE streaming
    """
    import asyncio
    
    # Generate session_id if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        # Load checkpoint for context
        checkpoint = await checkpoint_manager.load_checkpoint(session_id)
        messages_history = checkpoint.get("messages", []) if checkpoint else []
        
        # Add user message to history
        await checkpoint_manager.add_message(session_id, "user", prompt)
        
        # Build prompt with conversation history
        conversation_context = ""
        if messages_history:
            # Include last 10 messages for context
            recent_messages = messages_history[-10:]
            conversation_context = "\n\nPrevious conversation:\n"
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_context += f"{role.capitalize()}: {content}\n"
        
        full_prompt = prompt
        if conversation_context:
            full_prompt = f"{prompt}\n\n{conversation_context}"
        
        initial_state = {
            "messages": [HumanMessage(content=full_prompt)]
        }
        
        logger.info(f"Starting supervisor stream for session {session_id}")
        
        # Yield initial thinking event
        yield {
            "event": "thinking",
            "data": {"message": "Analyzing your request..."},
            "id": None
        }
        
        # Stream supervisor execution
        supervisor_graph = get_supervisor_graph()
        
        try:
            async for event in supervisor_graph.astream(initial_state):
                # Process LangGraph events
                if isinstance(event, dict):
                    # Check for agent transitions
                    for node_name, node_data in event.items():
                        if node_name != "__end__":
                            yield {
                                "event": "log",
                                "data": {
                                    "type": "agent_transition",
                                    "message": f"Using {node_name}..."
                                },
                                "id": None
                            }
                            
                            # Check for messages in node data
                            if isinstance(node_data, dict) and "messages" in node_data:
                                for message in node_data["messages"]:
                                    if hasattr(message, "tool_calls") and message.tool_calls:
                                        for tool_call in message.tool_calls:
                                            yield {
                                                "event": "tool_call",
                                                "data": {
                                                    "tool": tool_call.get("name", "unknown"),
                                                    "input": tool_call.get("args", {})
                                                },
                                                "id": None
                                            }
                
                await asyncio.sleep(0.1)
            
            # Get final state
            final_state = await supervisor_graph.ainvoke(initial_state)
            
            # Process final response
            messages = final_state.get("messages", [])
            if messages:
                last_message = messages[-1]
                content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                
                # Try to parse JSON
                parsed_content = None
                if isinstance(content, str):
                    try:
                        if content.strip().startswith("{") or content.strip().startswith("["):
                            parsed_content = json.loads(content)
                    except json.JSONDecodeError:
                        pass
                
                # Format response
                if parsed_content:
                    response_content = parsed_content
                elif isinstance(content, str):
                    response_content = content
                else:
                    response_content = str(content)
                
                # Save assistant response to checkpoint
                await checkpoint_manager.add_message(
                    session_id,
                    "assistant",
                    json.dumps(response_content) if isinstance(response_content, dict) else str(response_content)
                )
                
                # Yield final response
                yield {
                    "event": "done",
                    "data": {
                        "content": response_content,
                        "complete": True,
                        "session_id": session_id
                    },
                    "id": None
                }
            else:
                yield {
                    "event": "error",
                    "data": {"message": "No response generated"},
                    "id": None
                }
                
        except asyncio.TimeoutError:
            logger.error("Supervisor stream timed out")
            yield {
                "event": "error",
                "data": {"message": "Request timed out. Please try again."},
                "id": None
            }
            
    except Exception as e:
        logger.error(f"Error in supervisor stream: {e}", exc_info=True)
        yield {
            "event": "error",
            "data": {"message": f"Error processing request: {str(e)}"},
            "id": None
        }


async def run_supervisor(prompt: str, context: dict = None, session_id: str = None) -> dict:
    """Run the supervisor graph with a user prompt.
    
    Args:
        prompt: User's natural language prompt
        context: Additional context (optional, can be included in prompt)
        session_id: Session identifier
        
    Returns:
        Final agent output with type and content
    """
    try:
        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2)
            full_prompt = f"{prompt}\n\nAdditional context: {context_str}"
        
        initial_state = {
            "messages": [HumanMessage(content=full_prompt)]
        }
        
        supervisor_graph = get_supervisor_graph()
        final_state = await supervisor_graph.ainvoke(initial_state)
        
        messages = final_state.get("messages", [])
        if messages:
            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            try:
                if isinstance(content, str) and (content.strip().startswith("{") or content.strip().startswith("[")):
                    parsed_content = json.loads(content)
                    return {
                        "type": "output",
                        "content": parsed_content
                    }
            except json.JSONDecodeError:
                pass
            
            return {
                "type": "output",
                "content": content
            }
        else:
            return {
                "type": "output",
                "content": "No response generated"
            }
            
    except Exception as e:
        logger.error(f"Error running supervisor: {e}", exc_info=True)
        return {
            "type": "error",
            "content": f"Error processing request: {str(e)}"
        }


# ============================================================================
# Direct Agent Functions
# ============================================================================

async def run_planner_agent(prompt: str, context: dict = None) -> dict:
    """Run the planner agent directly to create a meal plan.
    
    Args:
        prompt: User's prompt describing their diet plan requirements
        context: Additional context (nutrition goals, preferences, location, budget)
        
    Returns:
        Dictionary with meal plan data
    """
    import asyncio
    
    try:
        # Build comprehensive prompt with context
        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2)
            full_prompt = f"""Create a personalized diet plan based on the following information:

User Request: {prompt}

Context:
{context_str}

Please create a complete meal plan based on the user's preferences. The number of meals per day should match the user's preference (if specified in context).

For each meal, provide:
- Meal name
- Description
- Calories
- Protein (grams)
- Carbs (grams)
- Fats (grams)
- Time of day

Format your response as a JSON object with this structure:
{{
  "goal": "user's fitness goal",
  "daily_calories": total_calories,
  "meals_per_day": number_of_meals,
  "meals": [
    {{
      "type": "Breakfast",
      "time": "8:00 AM",
      "name": "Meal name",
      "description": "Brief description",
      "calories": 500,
      "protein": 30,
      "carbs": 60,
      "fats": 15
    }}
  ],
  "summary": "Brief summary of the plan"
}}

If you need to use the create_meal_plan_from_results tool, you can pass empty strings for recipes_data, restaurants_data, and products_data, and just pass the nutrition_goals as JSON. Make sure to pass the meals_per_day parameter based on the user's preference."""
        
        initial_state = {
            "messages": [HumanMessage(content=full_prompt)]
        }
        
        logger.info("Starting planner agent invocation...")
        
        # Add timeout to prevent hanging (60 seconds)
        try:
            final_state = await asyncio.wait_for(
                planner_agent.ainvoke(initial_state),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            logger.error("Planner agent timed out after 60 seconds")
            # Generate a fallback response
            return {
                "type": "output",
                "content": {
                    "goal": context.get("goal", "general health") if context else "general health",
                    "daily_calories": context.get("daily_calories", 2000) if context else 2000,
                    "meals": [
                        {
                            "type": "Breakfast",
                            "time": "8:00 AM",
                            "name": "Oatmeal with fruits and nuts",
                            "description": "A balanced breakfast to start your day",
                            "calories": 400,
                            "protein": 15,
                            "carbs": 60,
                            "fats": 12
                        },
                        {
                            "type": "Lunch",
                            "time": "1:00 PM",
                            "name": "Grilled chicken salad",
                            "description": "High protein lunch with vegetables",
                            "calories": 500,
                            "protein": 40,
                            "carbs": 30,
                            "fats": 20
                        },
                        {
                            "type": "Dinner",
                            "time": "7:00 PM",
                            "name": "Salmon with quinoa and vegetables",
                            "description": "Nutritious dinner with omega-3s",
                            "calories": 600,
                            "protein": 45,
                            "carbs": 50,
                            "fats": 25
                        }
                    ],
                    "summary": "A balanced meal plan created based on your preferences. Please consult with a nutritionist for personalized advice."
                }
            }
        
        logger.info("Planner agent completed, processing response...")
        
        messages = final_state.get("messages", [])
        if messages:
            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            logger.info(f"Planner agent response type: {type(content)}, length: {len(str(content))}")
            
            # Try to parse JSON from the content
            try:
                if isinstance(content, str):
                    # Try to extract JSON from the string if it contains JSON
                    if content.strip().startswith("{") or content.strip().startswith("["):
                        parsed_content = json.loads(content)
                        return {
                            "type": "output",
                            "content": parsed_content
                        }
                    # Try to find JSON in the response
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        parsed_content = json.loads(json_match.group())
                        return {
                            "type": "output",
                            "content": parsed_content
                        }
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse JSON from response: {e}")
                # Continue to return as string
            
            # If content is a string, try to create a structured response
            if isinstance(content, str):
                # Check if it looks like a meal plan description
                return {
                    "type": "output",
                    "content": {
                        "summary": content,
                        "meals": []
                    }
                }
            
            return {
                "type": "output",
                "content": content
            }
        else:
            logger.warning("No messages in planner agent response")
            return {
                "type": "error",
                "content": "No response generated from planner agent"
            }
            
    except Exception as e:
        logger.error(f"Error running planner agent: {e}", exc_info=True)
        return {
            "type": "error",
            "content": f"Error processing request: {str(e)}"
        }


async def stream_planner_agent(prompt: str, session_id: str = None):
    """Stream planner agent execution with real-time logs.
    
    This agent acts as a nutrition expert, asking questions dynamically to understand
    the user's dietary needs and preferences, then creates a personalized meal plan.
    
    Args:
        prompt: User's prompt describing their diet plan requirements
        session_id: Session identifier for context continuity
        
    Yields:
        Dictionary events with type and data for SSE streaming
    """
    import asyncio
    
    # Hardcoded user_id for now
    USER_ID = "snehal"
    
    # Generate session_id if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        # Load checkpoint for context
        checkpoint = await checkpoint_manager.load_checkpoint(session_id)
        messages_history = checkpoint.get("messages", []) if checkpoint else []
        context = checkpoint.get("context", {}) if checkpoint else {}
        questionnaire = context.get("questionnaire", {}).copy() if context else {}
        is_generating_plan = context.get("is_generating_plan", False) if context else False
        
        # Add user message to history
        await checkpoint_manager.add_message(session_id, "user", prompt)
        
        # If user provided an answer, save it to users collection
        if context.get("waiting_for_answer"):
            # Save answer to users collection
            question_key = context.get("last_question_key", "unknown")
            questionnaire[question_key] = prompt.strip()
            context["questionnaire"] = questionnaire
            context["waiting_for_answer"] = False
            context["last_question_key"] = None
            
            # Save to users collection
            db = get_database()
            await db.users.update_one(
                {"user_id": USER_ID},
                {"$set": {
                    "questionnaire": questionnaire,
                    "session_id": session_id,
                    "last_updated": datetime.utcnow()
                }},
                upsert=True
            )
            
            await checkpoint_manager.update_context(session_id, context)
            logger.info(f"Saved answer for question '{question_key}' to users collection for user {USER_ID}")
        
        # Build conversation history for the agent
        conversation_messages = []
        if messages_history:
            # Convert checkpoint messages to LangChain message format
            for msg in messages_history[-20:]:  # Last 20 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    conversation_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    conversation_messages.append(AIMessage(content=content))
        
        # Add current user message
        conversation_messages.append(HumanMessage(content=prompt))
        
        # Build the prompt for the agent
        agent_prompt = prompt
        if questionnaire:
            questionnaire_summary = "\n\nInformation gathered so far:\n"
            for key, value in questionnaire.items():
                questionnaire_summary += f"- {key}: {value}\n"
            
            # Extract meals_per_day if available
            meals_per_day = None
            import re
            
            # First, check if meals_per_day key exists
            if "meals_per_day" in questionnaire:
                try:
                    answer = str(questionnaire["meals_per_day"]).lower()
                    numbers = re.findall(r'\d+', answer)
                    if numbers:
                        meals_per_day = int(numbers[0])
                except:
                    pass
            
            # If not found, search through all questionnaire answers for meal-related responses
            if meals_per_day is None:
                for key, value in questionnaire.items():
                    value_str = str(value).lower()
                    # Check if this answer mentions meals and contains a number
                    if any(word in value_str for word in ["meal", "eating", "times", "per day"]):
                        numbers = re.findall(r'\d+', value_str)
                        if numbers:
                            meals_per_day = int(numbers[0])
                            break
            
            # If meals_per_day is found, add explicit instruction
            if meals_per_day:
                questionnaire_summary += f"\nIMPORTANT: The user wants {meals_per_day} meals per day. Make sure to create exactly {meals_per_day} meals in the meal plan.\n"
            
            agent_prompt = f"{prompt}{questionnaire_summary}"
        
        # Create initial state with conversation history
        initial_state = {
            "messages": conversation_messages if len(conversation_messages) > 1 else [HumanMessage(content=agent_prompt)]
        }
        
        logger.info(f"Starting planner agent stream for session {session_id}, user_id: {USER_ID}")
        
        # Yield initial thinking event
        yield {
            "event": "thinking",
            "data": {"message": "Analyzing your request..."},
            "id": None
        }
        
        # Stream agent execution
        try:
            final_state = None
            
            # Stream the agent
            try:
                async for event in planner_agent.astream(initial_state):
                    if isinstance(event, dict):
                        # Store final state if we see __end__
                        if "__end__" in event:
                            final_state = event["__end__"]
                            break
                        
                        # Check for messages in the event
                        for node_name, node_data in event.items():
                            if node_name != "__end__" and isinstance(node_data, dict) and "messages" in node_data:
                                messages_list = node_data["messages"]
                                if messages_list:
                                    last_message = messages_list[-1]
                                    
                                    # Check if it's a tool call
                                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                                        for tool_call in last_message.tool_calls:
                                            tool_name = tool_call.get("name", "unknown") if isinstance(tool_call, dict) else getattr(tool_call, "name", "unknown")
                                            yield {
                                                "event": "tool_call",
                                                "data": {
                                                    "tool": tool_name,
                                                    "input": tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                                                },
                                                "id": None
                                            }
                    
                    await asyncio.sleep(0.05)
                
                # If we didn't get final state from stream, invoke to get final result
                if final_state is None:
                    logger.info("Getting final state from agent invocation")
                    try:
                        final_state = await asyncio.wait_for(
                            planner_agent.ainvoke(initial_state),
                            timeout=60.0
                        )
                    except (InternalServerError, RateLimitError, AnthropicError) as e:
                        logger.error(f"Anthropic API error during agent invocation: {e}", exc_info=True)
                        error_message = _get_user_friendly_error_message(e)
                        yield {
                            "event": "error",
                            "data": {"message": error_message},
                            "id": None
                        }
                        return
                    except asyncio.TimeoutError:
                        logger.error("Agent invocation timed out")
                        yield {
                            "event": "error",
                            "data": {"message": "Agent execution timed out. Please try again."},
                            "id": None
                        }
                        return
                    
            except (InternalServerError, RateLimitError, AnthropicError) as e:
                logger.error(f"Anthropic API error during agent stream: {e}", exc_info=True)
                error_message = _get_user_friendly_error_message(e)
                yield {
                    "event": "error",
                    "data": {"message": error_message},
                    "id": None
                }
                return
            except asyncio.TimeoutError:
                logger.error("Planner agent stream timed out")
                yield {
                    "event": "error",
                    "data": {"message": "Request timed out. Please try again."},
                    "id": None
                }
                return
            
            # Process final response
            messages = final_state.get("messages", [])
            if messages:
                last_message = messages[-1]
                content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                
                # Save assistant response to checkpoint
                await checkpoint_manager.add_message(session_id, "assistant", str(content))
                
                # Check if the response is a question or a meal plan
                content_str = str(content).strip()
                
                # Determine if this is a question or final meal plan
                # If it contains JSON with meals, it's a meal plan
                # Otherwise, it's likely a question
                is_question = True
                parsed_content = None
                
                # Try to parse as JSON (meal plan)
                try:
                    import re
                    json_match = re.search(r'(\{[\s\S]*\})', content_str)
                    if json_match:
                        parsed_content = json.loads(json_match.group(1))
                        # If it has "meals" key, it's a meal plan
                        if isinstance(parsed_content, dict) and "meals" in parsed_content:
                            is_question = False
                            is_generating_plan = True
                except (json.JSONDecodeError, Exception):
                    pass
                
                if is_question:
                    # Extract only the first question if multiple questions are present
                    single_question = _extract_single_question(content_str)
                    
                    # This is a question - save it and wait for answer
                    context["waiting_for_answer"] = True
                    context["last_question"] = single_question
                    # Generate a unique key for this question
                    question_key = f"question_{len(questionnaire) + 1}"
                    context["last_question_key"] = question_key
                    await checkpoint_manager.update_context(session_id, context)
                    
                    yield {
                        "event": "question",
                        "data": {
                            "question": single_question,
                            "question_key": question_key,
                            "answered": questionnaire,
                        },
                        "id": None
                    }
                    return
                else:
                    # This is a meal plan - save it to users collection
                    if parsed_content is None:
                        # Try to extract JSON from content
                        try:
                            import re
                            json_match = re.search(r'(\{[\s\S]*\})', content_str)
                            if json_match:
                                parsed_content = json.loads(json_match.group(1))
                        except Exception:
                            parsed_content = {
                                "summary": content_str,
                                "meals": []
                            }
                    
                    # Ensure proper structure
                    if isinstance(parsed_content, dict) and "meals" not in parsed_content:
                        parsed_content["meals"] = []
                    
                    # Save meal plan to users collection
                    db = get_database()
                    await db.users.update_one(
                        {"user_id": USER_ID},
                        {"$set": {
                            "questionnaire": questionnaire,
                            "meal_plan": parsed_content,
                            "session_id": session_id,
                            "finalize_diet_plan": True,
                            "last_updated": datetime.utcnow()
                        }},
                        upsert=True
                    )
                    
                    # Convert meal plan to DietCollection format and save to diet_collection
                    try:
                        diet_collections = _convert_meal_plan_to_diet_collection(USER_ID, parsed_content)
                        diet_collection = get_diet_collection()
                        
                        # Delete existing diet entries for this user to avoid duplicates
                        await diet_collection.delete_many({"user_id": USER_ID})
                        
                        # Insert new diet entries
                        if diet_collections:
                            await diet_collection.insert_many(diet_collections)
                            logger.info(f"Saved {len(diet_collections)} diet entries to diet_collection for user {USER_ID}")
                        else:
                            logger.warning(f"No diet entries to save for user {USER_ID}")
                    except Exception as e:
                        logger.error(f"Error saving meal plan to diet_collection: {e}", exc_info=True)
                        # Don't fail the whole operation if diet_collection save fails
                    
                    context["is_generating_plan"] = False
                    await checkpoint_manager.update_context(session_id, context)
                    
                    logger.info(f"Saved meal plan to users collection for user {USER_ID}")
                    
                    # Yield final response
                    yield {
                        "event": "done",
                        "data": {
                            "content": parsed_content,
                            "complete": True,
                            "session_id": session_id
                        },
                        "id": None
                    }
            else:
                yield {
                    "event": "error",
                    "data": {"message": "No response generated from planner agent"},
                    "id": None
                }
                
        except (InternalServerError, RateLimitError, AnthropicError) as e:
            logger.error(f"Anthropic API error in planner agent stream: {e}", exc_info=True)
            error_message = _get_user_friendly_error_message(e)
            yield {
                "event": "error",
                "data": {"message": error_message},
                "id": None
            }
        except asyncio.TimeoutError:
            logger.error("Planner agent stream timed out")
            yield {
                "event": "error",
                "data": {"message": "Request timed out. Please try again."},
                "id": None
            }
        except Exception as e:
            logger.error(f"Error in planner agent stream: {e}", exc_info=True)
            error_message = _get_user_friendly_error_message(e)
            yield {
                "event": "error",
                "data": {"message": error_message},
                "id": None
            }
            
    except (InternalServerError, RateLimitError, AnthropicError) as e:
        logger.error(f"Anthropic API error in planner agent stream: {e}", exc_info=True)
        error_message = _get_user_friendly_error_message(e)
        yield {
            "event": "error",
            "data": {"message": error_message},
            "id": None
        }
    except asyncio.TimeoutError:
        logger.error("Planner agent stream timed out")
        yield {
            "event": "error",
            "data": {"message": "Request timed out. Please try again."},
            "id": None
        }
    except Exception as e:
        logger.error(f"Error in planner agent stream: {e}", exc_info=True)
        error_message = _get_user_friendly_error_message(e)
        yield {
            "event": "error",
            "data": {"message": error_message},
            "id": None
        }


async def stream_restaurant_agent(prompt: str, session_id: str = None, context: Dict[str, Any] | None = None):
    """Stream restaurant agent execution."""
    import asyncio

    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        yield {
            "event": "thinking",
            "data": {"message": "Searching for the best restaurant options..."},
            "id": None
        }

        result = await run_restaurant_agent(prompt=prompt, context=context or {})

        if result.get("type") == "error":
            yield {
                "event": "error",
                "data": {"message": result.get("content", "Error finding restaurants")},
                "id": None
            }
            return

        content = result.get("content", {})
        formatted = format_restaurant_output(content)

        yield {
            "event": "done",
            "data": {"content": formatted, "session_id": session_id},
            "id": None
        }
    except asyncio.TimeoutError:
        yield {
            "event": "error",
            "data": {"message": "Restaurant search timed out. Please try again."},
            "id": None
        }
    except Exception as e:
        logger.error(f"Error in restaurant agent stream: {e}", exc_info=True)
        yield {
            "event": "error",
            "data": {"message": f"Error finding restaurants: {str(e)}"},
            "id": None
        }


async def stream_product_agent(prompt: str, session_id: str = None, context: Dict[str, Any] | None = None):
    """Stream product/online food agent execution."""
    import asyncio

    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        yield {
            "event": "thinking",
            "data": {"message": "Finding suitable products and online options..."},
            "id": None
        }

        result = await run_product_agent(prompt=prompt, context=context or {})

        if result.get("type") == "error":
            yield {
                "event": "error",
                "data": {"message": result.get("content", "Error finding products")},
                "id": None
            }
            return

        content = result.get("content", {})
        formatted = format_product_output(content)

        yield {
            "event": "done",
            "data": {"content": formatted, "session_id": session_id},
            "id": None
        }
    except asyncio.TimeoutError:
        yield {
            "event": "error",
            "data": {"message": "Product search timed out. Please try again."},
            "id": None
        }
    except Exception as e:
        logger.error(f"Error in product agent stream: {e}", exc_info=True)
        yield {
            "event": "error",
            "data": {"message": f"Error finding products: {str(e)}"},
            "id": None
        }


async def run_restaurant_agent(prompt: str, context: dict = None) -> dict:
    """Run the restaurant agent directly to find restaurants.
    
    Args:
        prompt: User's prompt describing restaurant search requirements
        context: Additional context (location, cuisine_type, budget, max_distance, search_query)
        
    Returns:
        Dictionary with restaurant data
    """
    try:
        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2)
            full_prompt = f"{prompt}\n\nAdditional context: {context_str}"
        
        initial_state = {
            "messages": [HumanMessage(content=full_prompt)]
        }
        
        final_state = await restaurant_agent.ainvoke(initial_state)
        
        messages = final_state.get("messages", [])
        if messages:
            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            try:
                if isinstance(content, str) and (content.strip().startswith("{") or content.strip().startswith("[")):
                    parsed_content = json.loads(content)
                    return {
                        "type": "output",
                        "content": parsed_content
                    }
            except json.JSONDecodeError:
                pass
            
            return {
                "type": "output",
                "content": content
            }
        else:
            return {
                "type": "error",
                "content": "No response generated from restaurant agent"
            }
            
    except Exception as e:
        logger.error(f"Error running restaurant agent: {e}", exc_info=True)
        return {
            "type": "error",
            "content": f"Error processing request: {str(e)}"
        }


async def run_product_agent(prompt: str, context: dict = None) -> dict:
    """Run the product agent directly to find products/online food options.
    
    Args:
        prompt: User's prompt describing product search requirements
        context: Additional context (search_query, nutrition_requirements, budget)
        
    Returns:
        Dictionary with product/online food data
    """
    try:
        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2)
            full_prompt = f"{prompt}\n\nAdditional context: {context_str}"
        
        initial_state = {
            "messages": [HumanMessage(content=full_prompt)]
        }
        
        final_state = await product_agent.ainvoke(initial_state)
        
        messages = final_state.get("messages", [])
        if messages:
            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            try:
                if isinstance(content, str) and (content.strip().startswith("{") or content.strip().startswith("[")):
                    parsed_content = json.loads(content)
                    return {
                        "type": "output",
                        "content": parsed_content
                    }
            except json.JSONDecodeError:
                pass
            
            return {
                "type": "output",
                "content": content
            }
        else:
            return {
                "type": "error",
                "content": "No response generated from product agent"
            }
            
    except Exception as e:
        logger.error(f"Error running product agent: {e}", exc_info=True)
        return {
            "type": "error",
            "content": f"Error processing request: {str(e)}"
        }


async def stream_goal_journey_agent(prompt: str, session_id: str = None, user_id: str = None):
    """Stream goal journey agent execution with real-time logs.
    
    This agent acts as a fitness coach, asking questions dynamically to understand
    the user's fitness goals and preferences, then creates/updates a personalized goal.
    
    Args:
        prompt: User's prompt/message
        session_id: Session identifier for context continuity
        user_id: User identifier (optional, can be extracted from context)
        
    Yields:
        Dictionary events with 'event' and 'data' keys for WebSocket streaming
    """
    import uuid
    
    # Generate session_id if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Use generic stream agent service
    async for event in stream_agent_service.stream_agent(
        agent=goal_journey_agent,
        prompt=prompt,
        session_id=session_id,
        user_id=user_id
    ):
        yield event