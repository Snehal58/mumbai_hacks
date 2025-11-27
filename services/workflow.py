"""Workflow for all agents and supervisor."""

from typing import Any, Dict, List
from langgraph_supervisor import create_supervisor
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from tools.recipe_tools import search_recipes
from tools.restaurant_tools import search_restaurants, estimate_meal_nutrition
from tools.product_tools import search_products
from tools.planner_tools import create_meal_plan_from_results
from prompts.recipe_agent_prompt import RECIPE_AGENT_PROMPT
from prompts.restaurant_agent_prompt import RESTAURANT_AGENT_PROMPT
from prompts.product_agent_prompt import PRODUCT_AGENT_PROMPT
from prompts.planner_agent_prompt import PLANNER_AGENT_PROMPT
from prompts.supervisor_prompt import SUPERVISOR_PROMPT
from utils.logger import setup_logger
from services.checkpoint import checkpoint_manager
from services.llm_factory import get_llm
import json
import uuid

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
    tools=[create_meal_plan_from_results],
    name="planner_agent",
    prompt=PLANNER_AGENT_PROMPT.template,
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

Please create a complete meal plan with:
- Breakfast
- Lunch  
- Dinner
- Optional snacks

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

If you need to use the create_meal_plan_from_results tool, you can pass empty strings for recipes_data, restaurants_data, and products_data, and just pass the nutrition_goals as JSON."""
        
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
    
    Args:
        prompt: User's prompt describing their diet plan requirements
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
        context = checkpoint.get("context", {}) if checkpoint else {}
        questionnaire = context.get("questionnaire", {}).copy() if context else {}
        pending_question = context.get("pending_question") if context else None
        questionnaire_complete = context.get("questionnaire_complete", False) if context else False
        
        # Add user message to history
        await checkpoint_manager.add_message(session_id, "user", prompt)

        # If we were waiting for an answer, capture it
        if pending_question:
            questionnaire[pending_question] = prompt.strip()
            context["questionnaire"] = questionnaire
            context["pending_question"] = None
            await checkpoint_manager.update_context(session_id, context)
            await checkpoint_manager.add_message(
                session_id,
                "system",
                f"{pending_question}: {prompt.strip()}",
            )
        
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
        
        next_question = None
        if not questionnaire_complete:
            next_question = _get_next_planner_question(questionnaire)
        
        if next_question:
            question_text = next_question["question"]
            context["pending_question"] = next_question["key"]
            context["questionnaire"] = questionnaire
            context["questionnaire_complete"] = False
            await checkpoint_manager.update_context(session_id, context)
            await checkpoint_manager.add_message(session_id, "assistant", question_text)
            
            yield {
                "event": "question",
                "data": {
                    "question": question_text,
                    "question_key": next_question["key"],
                    "answered": questionnaire,
                },
                "id": None
            }
            return
        else:
            if not questionnaire_complete and questionnaire:
                context["questionnaire_complete"] = True
                context["questionnaire"] = questionnaire
                context["pending_question"] = None
                await checkpoint_manager.update_context(session_id, context)
        
        # Build context string from checkpoint context
        context_str = ""
        if context:
            context_str = "\n\nAdditional Context:\n"
            for key, value in context.items():
                if key not in {"questionnaire", "pending_question", "questionnaire_complete"}:
                    context_str += f"- {key}: {value}\n"

        preferences_summary = _format_questionnaire_summary(questionnaire)
        if preferences_summary:
            context_str += "\n\nUser Preferences Provided:\n"
            context_str += preferences_summary
        
        # Build comprehensive prompt
        full_prompt = f"""Create a personalized diet plan based on the following information:

User Request: {prompt}
{conversation_context}{context_str}

Please create a complete meal plan with:
- Breakfast
- Lunch  
- Dinner
- Optional snacks

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
}}"""
        
        initial_state = {
            "messages": [HumanMessage(content=full_prompt)]
        }
        
        logger.info(f"Starting planner agent stream for session {session_id}")
        
        # Yield initial thinking event immediately
        yield {
            "event": "thinking",
            "data": {"message": "Analyzing your request and creating a personalized diet plan..."},
            "id": None
        }
        
        logger.info("Yielded initial thinking event, starting agent stream...")
        
        # Yield a log event to ensure connection is alive
        yield {
            "event": "log",
            "data": {"type": "status", "message": "Initializing planner agent..."},
            "id": None
        }
        
        # Stream agent execution with timeout
        try:
            final_state = None
            event_received = False
            
            # Try to stream, but if it doesn't yield events, fall back to ainvoke
            try:
                logger.info("Starting planner_agent.astream()...")
                
                # Use a timeout to ensure we don't hang forever
                stream_start = asyncio.get_event_loop().time()
                timeout = 90.0
                
                async for event in planner_agent.astream(initial_state):
                    event_received = True
                    elapsed = asyncio.get_event_loop().time() - stream_start
                    
                    if elapsed > timeout:
                        logger.warning(f"Stream exceeded {timeout}s, breaking to use ainvoke")
                        break
                    
                    logger.debug(f"Received event: {type(event)}")
                    
                    # Process LangGraph events
                    if isinstance(event, dict):
                        # Store final state if we see __end__
                        if "__end__" in event:
                            final_state = event["__end__"]
                            logger.info("Received __end__ event from stream")
                            break
                        
                        # Check for messages
                        if "messages" in event:
                            messages_list = event["messages"]
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
                                
                                # Check if it's a content message
                                if hasattr(last_message, "content") and last_message.content:
                                    content = last_message.content
                                    if isinstance(content, str) and len(content) > 50:
                                        yield {
                                            "event": "log",
                                            "data": {
                                                "type": "agent_response",
                                                "message": content[:200] + "..." if len(content) > 200 else content
                                            },
                                            "id": None
                                        }
                    
                    await asyncio.sleep(0.05)
                
                logger.info(f"Stream completed. Events received: {event_received}, Final state: {final_state is not None}")
                
                # If we didn't get final state from stream, invoke to get final result
                if final_state is None:
                    logger.info("Getting final state from agent invocation (stream didn't provide final state)")
                    try:
                        final_state = await asyncio.wait_for(
                            planner_agent.ainvoke(initial_state),
                            timeout=60.0
                        )
                        logger.info("Successfully got final state from ainvoke")
                    except asyncio.TimeoutError:
                        logger.error("Agent invocation timed out")
                        yield {
                            "event": "error",
                            "data": {"message": "Agent execution timed out. Please try again with a simpler request."},
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
                    response_content = {"summary": content, "meals": []}
                else:
                    response_content = content
                
                # Ensure proper structure
                if isinstance(response_content, dict) and "meals" not in response_content:
                    response_content = {"meals": [], "summary": str(response_content)}
                
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
                    "data": {"message": "No response generated from planner agent"},
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
        yield {
            "event": "error",
            "data": {"message": f"Error processing request: {str(e)}"},
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