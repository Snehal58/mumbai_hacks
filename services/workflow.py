"""Workflow for all agents and supervisor."""

from langgraph_supervisor import create_supervisor
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from config.settings import settings
from config.agent_config import AGENT_CONFIG
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
import json

logger = setup_logger(__name__)


# ============================================================================
# Agent LLM Initializations
# ============================================================================

recipe_llm = ChatOpenAI(
    model=AGENT_CONFIG["recipe_agent"]["model"],
    temperature=AGENT_CONFIG["recipe_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

restaurant_llm = ChatOpenAI(
    model=AGENT_CONFIG["restaurant_agent"]["model"],
    temperature=AGENT_CONFIG["restaurant_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

product_llm = ChatOpenAI(
    model=AGENT_CONFIG["product_agent"]["model"],
    temperature=AGENT_CONFIG["product_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

planner_llm = ChatOpenAI(
    model=AGENT_CONFIG["planner_agent"]["model"],
    temperature=AGENT_CONFIG["planner_agent"]["temperature"],
    api_key=settings.openai_api_key,
)

supervisor_llm = ChatOpenAI(
    model=AGENT_CONFIG["supervisor"]["model"],
    temperature=AGENT_CONFIG["supervisor"]["temperature"],
    api_key=settings.openai_api_key,
)


# ============================================================================
# Agent Declarations
# ============================================================================

# Recipe Agent
recipe_agent = create_react_agent(
    model=recipe_llm,
    tools=[search_recipes],
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
