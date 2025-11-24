"""LangGraph Supervisor for orchestrating multiple agents."""

from typing import TypedDict, Annotated, Literal, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from config.settings import settings
from config.agent_config import AGENT_CONFIG, AGENT_ROUTING
from agents.nlp_agent import parse_request
from agents.planner_agent import create_meal_plan
from agents.recipe_agent import find_recipes
from agents.restaurant_agent import find_restaurant_meals
from agents.product_agent import find_products
from agents.nutrition_agent import analyze_meal_plan
from models.schemas import ParsedRequest, NutritionGoal, MealContext
from utils.logger import setup_logger
import json

logger = setup_logger(__name__)


class AgentState(TypedDict):
    """State passed between agents."""
    messages: Annotated[list, "messages"]
    parsed_request: ParsedRequest
    current_step: str
    agent_output: dict
    session_id: str
    recipes: Optional[List]  # Store recipe results
    restaurant_meals: Optional[List]  # Store restaurant results
    products: Optional[List]  # Store product results


# Initialize supervisor LLM
supervisor_llm = ChatOpenAI(
    model=AGENT_CONFIG["supervisor"]["model"],
    temperature=AGENT_CONFIG["supervisor"]["temperature"],
    api_key=settings.openai_api_key,
)


def route_after_nlp(state: AgentState) -> str:
    """Route to appropriate agents based on parsed intent.
    
    Returns:
        Next node name or "planner_agent" if all agents are done
    """
    parsed_request = state.get("parsed_request")
    if not parsed_request or not parsed_request.intent:
        # Default: go to planner if no intent detected
        return "planner_agent"
    
    intent = parsed_request.intent
    
    # Check which agents have been called (None means not called yet)
    recipes_done = state.get("recipes") is not None
    restaurants_done = state.get("restaurant_meals") is not None
    products_done = state.get("products") is not None
    
    # Priority order: recipes -> restaurants -> products
    # Route to first agent that's needed and not done
    if "recipes" in intent and not recipes_done:
        return "recipe_agent"
    elif "restaurants" in intent and not restaurants_done:
        return "restaurant_agent"
    elif "products" in intent and not products_done:
        return "product_agent"
    else:
        # All requested agents are done, go to planner
        return "planner_agent"


def route_after_agent(state: AgentState) -> str:
    """Route after a specific agent has completed.
    
    Determines if more agents need to be called or if we should go to planner.
    This function is called after recipe_agent, restaurant_agent, or product_agent.
    """
    parsed_request = state.get("parsed_request")
    if not parsed_request or not parsed_request.intent:
        return "planner_agent"
    
    intent = parsed_request.intent
    
    # Check which agents have been called
    recipes_done = state.get("recipes") is not None
    restaurants_done = state.get("restaurant_meals") is not None
    products_done = state.get("products") is not None
    
    # Check what still needs to be done (priority order)
    if "recipes" in intent and not recipes_done:
        return "recipe_agent"
    elif "restaurants" in intent and not restaurants_done:
        return "restaurant_agent"
    elif "products" in intent and not products_done:
        return "product_agent"
    else:
        # All requested agents are done, go to planner
        return "planner_agent"


def create_supervisor_graph():
    """Create the LangGraph supervisor graph with dynamic routing."""
    
    # Define agent nodes (async for async agent functions)
    async def nlp_agent_node(state: AgentState) -> AgentState:
        """Natural Language Understanding agent node."""
        try:
            # Extract prompt from messages
            prompt = state["messages"][-1] if state["messages"] else ""
            if isinstance(prompt, dict):
                prompt = prompt.get("content", "")
            
            context = state.get("context", {})
            parsed = await parse_request(prompt, context)
            
            return {
                **state,
                "parsed_request": parsed,
                "current_step": "nlp_agent",
                "agent_output": {
                    "type": "thinking",
                    "content": "Parsed user request successfully",
                    "parsed_data": parsed.dict()
                }
            }
        except Exception as e:
            logger.error(f"Error in NLP agent: {e}")
            return {
                **state,
                "current_step": "error",
                "agent_output": {
                    "type": "error",
                    "content": f"Error parsing request: {str(e)}"
                }
            }
    
    async def recipe_agent_node(state: AgentState) -> AgentState:
        """Recipe Finder agent node."""
        try:
            parsed_request = state.get("parsed_request")
            if not parsed_request:
                return state
            
            recipes = await find_recipes(
                parsed_request.nutrition_goals,
                parsed_request.meal_context,
                max_results=5
            )
            
            return {
                **state,
                "recipes": recipes,  # Store in state
                "current_step": "recipe_agent",
                "agent_output": {
                    "type": "finding_records",
                    "content": f"Found {len(recipes)} recipes",
                    "recipes": [r.dict() for r in recipes]
                }
            }
        except Exception as e:
            logger.error(f"Error in Recipe agent: {e}")
            return {
                **state,
                "recipes": [],
                "current_step": "error",
                "agent_output": {
                    "type": "error",
                    "content": f"Error finding recipes: {str(e)}"
                }
            }
    
    async def restaurant_agent_node(state: AgentState) -> AgentState:
        """Restaurant Finder agent node."""
        try:
            parsed_request = state.get("parsed_request")
            if not parsed_request or not parsed_request.meal_context:
                return state
            
            restaurant_meals = await find_restaurant_meals(
                parsed_request.meal_context,
                max_results=5
            )
            
            return {
                **state,
                "restaurant_meals": restaurant_meals,  # Store in state
                "current_step": "restaurant_agent",
                "agent_output": {
                    "type": "searching_more",
                    "content": f"Found {len(restaurant_meals)} restaurant options",
                    "restaurants": [r.dict() for r in restaurant_meals]
                }
            }
        except Exception as e:
            logger.error(f"Error in Restaurant agent: {e}")
            return {
                **state,
                "restaurant_meals": [],
                "current_step": "error",
                "agent_output": {
                    "type": "error",
                    "content": f"Error finding restaurants: {str(e)}"
                }
            }
    
    async def product_agent_node(state: AgentState) -> AgentState:
        """Product Finder agent node."""
        try:
            parsed_request = state.get("parsed_request")
            if not parsed_request:
                return state
            
            products = await find_products(
                parsed_request.nutrition_goals,
                product_type="protein supplement",
                max_results=3
            )
            
            return {
                **state,
                "products": products,  # Store in state
                "current_step": "product_agent",
                "agent_output": {
                    "type": "searching_more",
                    "content": f"Found {len(products)} product options",
                    "products": [p.dict() for p in products]
                }
            }
        except Exception as e:
            logger.error(f"Error in Product agent: {e}")
            return {
                **state,
                "products": [],
                "current_step": "error",
                "agent_output": {
                    "type": "error",
                    "content": f"Error finding products: {str(e)}"
                }
            }
    
    async def planner_agent_node(state: AgentState) -> AgentState:
        """Planning/Orchestration agent node."""
        try:
            parsed_request = state.get("parsed_request")
            if not parsed_request:
                return state
            
            # Get results from state (from previous agents)
            recipes = state.get("recipes", [])
            restaurant_meals = state.get("restaurant_meals", [])
            products = state.get("products", [])
            
            # Create meal plan using results from state
            output = await create_meal_plan(
                parsed_request,
                recipes=recipes,
                restaurant_meals=restaurant_meals,
                products=products
            )
            
            return {
                **state,
                "current_step": "planner_agent",
                "agent_output": {
                    "type": "output",
                    "content": output.dict()
                }
            }
        except Exception as e:
            logger.error(f"Error in Planner agent: {e}")
            return {
                **state,
                "current_step": "error",
                "agent_output": {
                    "type": "error",
                    "content": f"Error creating meal plan: {str(e)}"
                }
            }
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("nlp_agent", nlp_agent_node)
    workflow.add_node("recipe_agent", recipe_agent_node)
    workflow.add_node("restaurant_agent", restaurant_agent_node)
    workflow.add_node("product_agent", product_agent_node)
    workflow.add_node("planner_agent", planner_agent_node)
    
    # Define the flow with conditional routing
    workflow.set_entry_point("nlp_agent")
    
    # After NLP agent, route based on intent
    workflow.add_conditional_edges(
        "nlp_agent",
        route_after_nlp,
        {
            "recipe_agent": "recipe_agent",
            "restaurant_agent": "restaurant_agent",
            "product_agent": "product_agent",
            "planner_agent": "planner_agent"
        }
    )
    
    # After recipe agent, check if more agents needed
    workflow.add_conditional_edges(
        "recipe_agent",
        route_after_agent,
        {
            "restaurant_agent": "restaurant_agent",
            "product_agent": "product_agent",
            "planner_agent": "planner_agent"
        }
    )
    
    # After restaurant agent, check if more agents needed
    workflow.add_conditional_edges(
        "restaurant_agent",
        route_after_agent,
        {
            "recipe_agent": "recipe_agent",
            "product_agent": "product_agent",
            "planner_agent": "planner_agent"
        }
    )
    
    # After product agent, check if more agents needed
    workflow.add_conditional_edges(
        "product_agent",
        route_after_agent,
        {
            "recipe_agent": "recipe_agent",
            "restaurant_agent": "restaurant_agent",
            "planner_agent": "planner_agent"
        }
    )
    
    # Planner always goes to END
    workflow.add_edge("planner_agent", END)
    
    return workflow.compile()


# Create the supervisor graph instance
supervisor_graph = create_supervisor_graph()


async def run_supervisor(prompt: str, context: dict = None, session_id: str = None) -> dict:
    """Run the supervisor graph with a user prompt.
    
    Args:
        prompt: User's natural language prompt
        context: Additional context
        session_id: Session identifier
        
    Returns:
        Final agent output
    """
    initial_state = {
        "messages": [prompt],
        "parsed_request": None,
        "current_step": "start",
        "agent_output": {},
        "session_id": session_id or "",
        "context": context or {},
        "recipes": None,
        "restaurant_meals": None,
        "products": None
    }
    
    try:
        # Run the graph (use ainvoke for async nodes)
        final_state = await supervisor_graph.ainvoke(initial_state)
        return final_state.get("agent_output", {})
    except Exception as e:
        logger.error(f"Error running supervisor: {e}")
        return {
            "type": "error",
            "content": f"Error processing request: {str(e)}"
        }

