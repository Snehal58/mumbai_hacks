"""REST API routes (optional, for non-WebSocket endpoints)."""

from typing import Any, Callable, Dict, Optional, Tuple, Type
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from models.database import get_database, get_users_collection
from models.schemas import (
    WebSocketMessage,
    PlannerRequest,
    RestaurantRequest,
    ProductRequest,
    RecipeRequest,
    GoalImpactRequest,
    GoalImpactResponse,
    MealNutritionRequest,
    MealNutritionResponse,
    User
)
from services.workflow import (
    run_supervisor,
    run_planner_agent,
    run_restaurant_agent,
    run_product_agent,
    stream_planner_agent,
    stream_supervisor,
    stream_restaurant_agent,
    stream_product_agent,
    stream_goal_journey_agent,
    format_restaurant_output,
    format_product_output
)
from utils.logger import setup_logger
import json
import uuid

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])

@router.post("/users", response_model=User)
async def create_user(user: User):
    """Create a new user."""
    try:
        users_collection = get_users_collection()
        
        # Check if user already exists
        existing_user = await users_collection.find_one({"user_id": user.user_id})
        if existing_user:
            raise HTTPException(status_code=400, detail=f"User with user_id '{user.user_id}' already exists")
        
        # Insert user
        result = await users_collection.insert_one(user.model_dump())
        
        if result.inserted_id:
            logger.info(f"Created user: {user.user_id}")
            return user
        else:
            raise HTTPException(status_code=500, detail="Failed to create user")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@router.get("/meals")
async def get_meals():
    """Get list of available meals.""" 
    try:
        db = get_database()
        user = await db.users.find_one({"user_id": "123"}) # TODO: This user_id will be pulled using auth token

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Extract only meal_plan
        meal_plan = user.get("meal_plan")

        return meal_plan
    except Exception as e:
        logger.error(f"Error fetching meals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching meals: {str(e)}")

@router.get("/is_onboarded")
async def is_onboarded():
    """Get list of available meals.""" 
    try:
        db = get_database()
        user = await db.users.find_one({"user_id": "123"}) # TODO: This user_id will be pulled using auth token

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Extract only meal_plan
        is_onboarded = user.get("finalize_diet_plan")

        return {"is_onboarded": is_onboarded}
    except Exception as e:
        logger.error(f"Error fetching meals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching meals: {str(e)}")

def format_sse_event(event_type: str, data: dict, event_id: str = None) -> str:
    """Format data as Server-Sent Event.
    
    Args:
        event_type: Event type (log, thinking, tool_call, response, done, error)
        data: Event data dictionary
        event_id: Optional event ID
        
    Returns:
        Formatted SSE string
    """
    lines = [f"event: {event_type}"]
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # Empty line to signal end of event
    return "\n".join(lines)


def build_restaurant_prompt(request: RestaurantRequest, base_context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    context = base_context.copy()
    prompt_parts = []
    if request.prompt:
        prompt_parts.append(request.prompt)
    else:
        prompt_parts.append("Find restaurants")

    if request.location:
        prompt_parts.append(f"near {request.location}")
        context["location"] = request.location
    if request.cuisine_type:
        prompt_parts.append(f"serving {request.cuisine_type} cuisine")
        context["cuisine_type"] = request.cuisine_type
    if request.search_query:
        prompt_parts.append(f"matching '{request.search_query}'")
        context["search_query"] = request.search_query
    if request.budget is not None:
        context["budget"] = request.budget
    if request.max_distance is not None:
        context["max_distance"] = request.max_distance

    prompt = " ".join(prompt_parts).strip()
    return prompt, context


def build_product_prompt(request: ProductRequest, base_context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    context = base_context.copy()
    prompt_parts = []
    if request.prompt:
        prompt_parts.append(request.prompt)
    else:
        prompt_parts.append("Find nutrition products or online food options")

    if request.search_query:
        prompt_parts.append(f"matching '{request.search_query}'")
        context["product_search_query"] = request.search_query
    if request.nutrition_requirements:
        context["nutrition_requirements"] = request.nutrition_requirements
    if request.budget is not None:
        context["product_budget"] = request.budget

    prompt = " ".join(prompt_parts).strip()
    return prompt, context


StreamKwargsBuilder = Callable[[BaseModel, Dict[str, Any], str], Tuple[Dict[str, Any], Optional[Dict[str, Any]]]]


async def handle_agent_websocket_connection(
    websocket: WebSocket,
    agent_name: str,
    request_model: Type[BaseModel],
    stream_fn: Callable[..., Any],
    stream_kwargs_builder: StreamKwargsBuilder,
):
    from services.checkpoint import checkpoint_manager

    session_id = str(uuid.uuid4())
    try:
        await websocket.accept()
        await websocket.send_json({
            "event": "connected",
            "data": {"message": f"Connected to {agent_name} stream", "session_id": session_id},
            "session_id": session_id
        })

        try:
            raw_message = await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info(f"{agent_name} WebSocket disconnected before receiving payload.")
            return

        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await websocket.send_json({
                "event": "error",
                "data": {"message": "Invalid message format"},
                "session_id": session_id
            })
            return

        try:
            request_obj = request_model(**payload)
        except ValidationError as exc:
            await websocket.send_json({
                "event": "error",
                "data": {"message": "Invalid request data", "details": json.loads(exc.json())},
                "session_id": session_id
            })
            return

        current_session_id = getattr(request_obj, "session_id", None) or session_id
        if getattr(request_obj, "session_id", None):
            session_id = current_session_id

        context: Dict[str, Any] = {}
        if getattr(request_obj, "session_id", None):
            checkpoint = await checkpoint_manager.load_checkpoint(current_session_id)
            if checkpoint:
                context = checkpoint.get("context", {}).copy()

        stream_kwargs, updated_context = stream_kwargs_builder(request_obj, context, current_session_id)

        if updated_context is not None and getattr(request_obj, "session_id", None):
            await checkpoint_manager.update_context(current_session_id, updated_context)

        async for event in stream_fn(**stream_kwargs):
            event_type = event.get("event", "log")
            await websocket.send_json({
                "event": event_type,
                "data": event.get("data", {}),
                "session_id": current_session_id
            })
            if event_type in ("done", "error"):
                await websocket.close()
                return

    except WebSocketDisconnect:
        logger.info(f"{agent_name} WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"{agent_name} WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "event": "error",
                "data": {"message": f"Error processing request: {str(e)}"},
                "session_id": session_id
            })
        except Exception:
            pass
@router.get("/chat/stream")
async def chat_stream_endpoint(
    prompt: str = Query(..., description="User's chat message"),
    session_id: str = Query(None, description="Session identifier for context continuity")
):
    """SSE streaming endpoint for chat with real-time LLM logs."""
    try:
        # Generate session_id if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        logger.info(f"Starting chat stream for session {session_id}, prompt length: {len(prompt)}")
        
        async def event_generator():
            """Generate SSE events from supervisor stream."""
            try:
                async for event in stream_supervisor(prompt=prompt, session_id=session_id):
                    event_type = event.get("event", "log")
                    event_data = event.get("data", {})
                    event_id = event.get("id")
                    
                    yield format_sse_event(event_type, event_data, event_id)
                    
            except Exception as e:
                logger.error(f"Error in chat event generator: {e}", exc_info=True)
                error_event = format_sse_event(
                    "error",
                    {"message": f"Stream error: {str(e)}"},
                    None
                )
                yield error_event
        
        response = StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )
        # Set headers for SSE with CORS
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Cache-Control, Content-Type"
        response.headers["Access-Control-Expose-Headers"] = "*"
        return response
        
    except Exception as e:
        logger.error(f"Error in chat stream endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting stream: {str(e)}")


@router.post("/chat")
async def chat_endpoint(message: WebSocketMessage):
    """REST endpoint for chat (alternative to WebSocket)."""
    try:
        result = await run_supervisor(
            prompt=message.prompt,
            context=message.context,
            session_id=message.session_id
        )
        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return {"error": str(e)}


@router.get("/planner/stream/test")
async def planner_stream_test():
    """Test endpoint to verify SSE streaming works."""
    import asyncio
    
    async def test_generator():
        yield format_sse_event("log", {"type": "test", "message": "SSE connection test successful"}, None)
        await asyncio.sleep(0.5)
        yield format_sse_event("log", {"type": "test", "message": "Sending test events..."}, None)
        await asyncio.sleep(0.5)
        yield format_sse_event("done", {"message": "Test complete", "status": "success"}, None)
    
    response = StreamingResponse(test_generator(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@router.get("/planner/stream")
async def planner_stream_endpoint(
    prompt: str = Query(..., description="User's prompt describing diet plan requirements"),
    session_id: str = Query(None, description="Session identifier for context continuity")
):
    """SSE streaming endpoint for planner agent with real-time LLM logs.
    
    Returns Server-Sent Events stream with:
    - thinking: Initial analysis
    - log: Intermediate logs and agent thoughts
    - tool_call: Tool invocations
    - response: Partial responses
    - done: Final complete response
    - error: Error messages
    """
    try:
        # Generate session_id if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        logger.info(f"Starting planner stream for session {session_id}, prompt length: {len(prompt)}")
        
        async def event_generator():
            """Generate SSE events from agent stream."""
            import asyncio
            
            try:
                # Send initial connection event
                yield format_sse_event("log", {"type": "connection", "message": "Connected to planner stream"}, None)
                
                last_keepalive = asyncio.get_event_loop().time()
                event_count = 0
                
                async for event in stream_planner_agent(prompt=prompt, session_id=session_id):
                    event_type = event.get("event", "log")
                    event_data = event.get("data", {})
                    event_id = event.get("id")
                    
                    yield format_sse_event(event_type, event_data, event_id)
                    event_count += 1
                    last_keepalive = asyncio.get_event_loop().time()
                    
                    # If we got a done or error event, break
                    if event_type in ("done", "error"):
                        break
                    
                    # Send keepalive every 10 seconds if no events
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_keepalive > 10:
                        yield format_sse_event("log", {"type": "keepalive", "message": "Still processing your request..."}, None)
                        last_keepalive = current_time
                    
            except Exception as e:
                logger.error(f"Error in event generator: {e}", exc_info=True)
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Full traceback: {error_details}")
                error_event = format_sse_event(
                    "error",
                    {"message": f"Stream error: {str(e)}", "details": str(e)},
                    None
                )
                yield error_event
        
        response = StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )
        # Set headers for SSE
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["X-Accel-Buffering"] = "no"  # Disable nginx buffering
        # CORS headers for SSE (EventSource requires these)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Cache-Control, Content-Type"
        response.headers["Access-Control-Expose-Headers"] = "*"
        return response
        
    except Exception as e:
        logger.error(f"Error in planner stream endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting stream: {str(e)}")


async def handle_planner_websocket(websocket: WebSocket):
    """Handle WebSocket connection for planner agent streaming."""
    session_id = str(uuid.uuid4())
    
    try:
        await websocket.accept()
        logger.info(f"Planner WebSocket connected: {session_id}")
        
        # Send connection confirmation
        await websocket.send_json({
            "event": "connected",
            "data": {"message": "Connected to planner stream", "session_id": session_id},
            "session_id": session_id
        })
        
        # Wait for initial message with prompt
        try:
            # Receive message from client
            message = await websocket.receive_text()
            data = json.loads(message)
            
            prompt = data.get("prompt")
            if not prompt:
                await websocket.send_json({
                    "event": "error",
                    "data": {"message": "Missing 'prompt' in message"},
                    "session_id": session_id
                })
                await websocket.close()
                return
            
            # Use provided session_id or use the one we generated
            provided_session_id = data.get("session_id") or session_id
            if provided_session_id != session_id:
                session_id = provided_session_id
            
            logger.info(f"Received planner request for session {session_id}, prompt length: {len(prompt)}")
            
            # Stream planner agent events
            async for event in stream_planner_agent(prompt=prompt, session_id=session_id):
                event_type = event.get("event", "log")
                event_data = event.get("data", {})
                
                # Send event to client
                await websocket.send_json({
                    "event": event_type,
                    "data": event_data,
                    "session_id": session_id
                })
                
                # Break if we got done or error event
                if event_type in ("done", "error"):
                    break
            
            # Close connection after completion
            await websocket.close()
            
        except WebSocketDisconnect:
            logger.info(f"Planner WebSocket disconnected: {session_id}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WebSocket message: {e}")
            await websocket.send_json({
                "event": "error",
                "data": {"message": "Invalid message format"},
                "session_id": session_id
            })
            await websocket.close()
        except Exception as e:
            logger.error(f"Error in planner WebSocket handler: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "event": "error",
                    "data": {"message": f"Error processing request: {str(e)}"},
                    "session_id": session_id
                })
                await websocket.close()
            except Exception:
                pass
    
    except WebSocketDisconnect:
        logger.info(f"Planner WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Planner WebSocket error: {e}", exc_info=True)


async def handle_goal_journey_websocket(websocket: WebSocket):
    """Handle WebSocket connection for goal journey agent streaming."""
    session_id = str(uuid.uuid4())
    
    try:
        await websocket.accept()
        logger.info(f"Goal Journey WebSocket connected: {session_id}")
        
        # Send connection confirmation
        await websocket.send_json({
            "event": "connected",
            "data": {"message": "Connected to goal journey stream", "session_id": session_id},
            "session_id": session_id
        })
        
        # Wait for initial message with prompt
        try:
            # Receive message from client
            message = await websocket.receive_text()
            data = json.loads(message)
            
            prompt = data.get("prompt")
            if not prompt:
                await websocket.send_json({
                    "event": "error",
                    "data": {"message": "Missing 'prompt' in message"},
                    "session_id": session_id
                })
                await websocket.close()
                return
            
            # Use provided session_id or use the one we generated
            provided_session_id = data.get("session_id") or session_id
            if provided_session_id != session_id:
                session_id = provided_session_id
            
            # Get user_id from data if provided
            user_id = data.get("user_id")
            
            logger.info(f"Received goal journey request for session {session_id}, user_id: {user_id}, prompt length: {len(prompt)}")
            
            # Stream goal journey agent events
            async for event in stream_goal_journey_agent(prompt=prompt, session_id=session_id, user_id=user_id):
                event_type = event.get("event", "log")
                event_data = event.get("data", {})
                
                # Send event to client
                await websocket.send_json({
                    "event": event_type,
                    "data": event_data,
                    "session_id": session_id
                })
                
                # Break if we got done or error event
                if event_type in ("done", "error"):
                    break
            
            # Close connection after completion
            await websocket.close()
            
        except WebSocketDisconnect:
            logger.info(f"Goal Journey WebSocket disconnected: {session_id}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in goal journey websocket message: {e}")
            await websocket.send_json({
                "event": "error",
                "data": {"message": "Invalid message format"},
                "session_id": session_id
            })
            await websocket.close()
        except Exception as e:
            logger.error(f"Error in goal journey websocket: {e}", exc_info=True)
            await websocket.send_json({
                "event": "error",
                "data": {"message": f"Error: {str(e)}"},
                "session_id": session_id
            })
            await websocket.close()
    except Exception as e:
        logger.error(f"Error setting up goal journey websocket: {e}", exc_info=True)


async def handle_restaurant_websocket(websocket: WebSocket):
    """Handle WebSocket connection for restaurant agent streaming."""

    def build_kwargs(
        request: RestaurantRequest,
        context: Dict[str, Any],
        session_id: str
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        prompt, updated_context = build_restaurant_prompt(request, context)
        stream_kwargs = {
            "prompt": prompt,
            "session_id": session_id,
            "context": updated_context or {}
        }
        return stream_kwargs, updated_context

    await handle_agent_websocket_connection(
        websocket,
        "restaurant",
        RestaurantRequest,
        stream_restaurant_agent,
        build_kwargs,
    )


async def handle_product_websocket(websocket: WebSocket):
    """Handle WebSocket connection for product agent streaming."""

    def build_kwargs(
        request: ProductRequest,
        context: Dict[str, Any],
        session_id: str
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        prompt, updated_context = build_product_prompt(request, context)
        stream_kwargs = {
            "prompt": prompt,
            "session_id": session_id,
            "context": updated_context or {}
        }
        return stream_kwargs, updated_context

    await handle_agent_websocket_connection(
        websocket,
        "product",
        ProductRequest,
        stream_product_agent,
        build_kwargs,
    )


@router.post("/planner")
async def planner_endpoint(request: PlannerRequest):
    """Direct planner agent endpoint for creating diet plans (non-streaming, for backward compatibility)."""
    import asyncio
    
    try:
        logger.info(f"Received planner request: prompt length={len(request.prompt)}, session_id={request.session_id}")
        
        # Load checkpoint if session_id provided
        context = {}
        if request.session_id:
            from services.checkpoint import checkpoint_manager
            checkpoint = await checkpoint_manager.load_checkpoint(request.session_id)
            if checkpoint:
                context = checkpoint.get("context", {})
        
        # Create a comprehensive prompt if not provided
        prompt = request.prompt
        if not prompt or len(prompt.strip()) < 10:
            prompt = "Create a personalized diet plan based on the provided context."
        
        # Add timeout wrapper (70 seconds total - 60 for agent + 10 for processing)
        try:
            result = await asyncio.wait_for(
                run_planner_agent(prompt=prompt, context=context),
                timeout=70.0
            )
        except asyncio.TimeoutError:
            logger.error("Planner endpoint timed out")
            raise HTTPException(
                status_code=504,
                detail="Request timed out. The planner is taking too long to respond. Please try again with a simpler request."
            )
        
        logger.info(f"Planner agent returned: type={result.get('type')}")
        
        if result.get("type") == "error":
            error_msg = result.get("content", "Unknown error")
            logger.error(f"Planner agent error: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Extract content and format for frontend
        content = result.get("content", {})
        
        logger.info(f"Processing content: type={type(content)}")
        
        # If content is a string, try to parse it
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                # If it's not JSON, wrap it in a meal plan structure
                content = {
                    "summary": content,
                    "meals": []
                }
        
        # Ensure the response matches frontend format
        if isinstance(content, dict):
            # Check if it already has the expected structure
            if "meals" not in content:
                # Try to extract meal plan from various possible structures
                if "meal_plan" in content:
                    meal_plan = content["meal_plan"]
                    if isinstance(meal_plan, dict) and "meals" in meal_plan:
                        content = meal_plan
                    else:
                        content = {"meals": [], "summary": str(meal_plan)}
                else:
                    # If no meals, create a basic structure
                    content = {"meals": [], "summary": str(content) if content else "Meal plan created"}
        
        # Ensure meals is a list
        if "meals" in content and not isinstance(content["meals"], list):
            content["meals"] = []
        
        logger.info(f"Returning response: plan_ready=True, meals_count={len(content.get('meals', []))}")
        
        return {
            "plan_ready": True,
            "diet_plan": content
        }
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Request timed out. Please try again."
        )
    except Exception as e:
        logger.error(f"Error in planner endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating diet plan: {str(e)}")


@router.post("/restaurants")
async def restaurants_endpoint(request: RestaurantRequest):
    """Direct restaurant agent endpoint for finding restaurants."""
    try:
        context: Dict[str, Any] = {}
        if request.session_id:
            from services.checkpoint import checkpoint_manager
            checkpoint = await checkpoint_manager.load_checkpoint(request.session_id)
            if checkpoint:
                context = checkpoint.get("context", {}).copy()

        prompt, updated_context = build_restaurant_prompt(request, context)

        if request.session_id and updated_context is not None:
            from services.checkpoint import checkpoint_manager
            await checkpoint_manager.update_context(request.session_id, updated_context)
        
        result = await run_restaurant_agent(prompt=prompt, context=updated_context or {})
        
        if result.get("type") == "error":
            raise HTTPException(status_code=500, detail=result.get("content", "Unknown error"))
        
        # Extract content
        content = result.get("content", {})
        formatted = format_restaurant_output(content)
        return formatted
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in restaurants endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error finding restaurants: {str(e)}")


@router.post("/products")
async def products_endpoint(request: ProductRequest):
    """Direct product agent endpoint for finding products/online food options."""
    try:
        context: Dict[str, Any] = {}
        if request.session_id:
            from services.checkpoint import checkpoint_manager
            checkpoint = await checkpoint_manager.load_checkpoint(request.session_id)
            if checkpoint:
                context = checkpoint.get("context", {}).copy()
        
        prompt, updated_context = build_product_prompt(request, context)
        
        if request.session_id and updated_context is not None:
            from services.checkpoint import checkpoint_manager
            await checkpoint_manager.update_context(request.session_id, updated_context)
        
        result = await run_product_agent(prompt=prompt, context=updated_context or {})
        
        if result.get("type") == "error":
            raise HTTPException(status_code=500, detail=result.get("content", "Unknown error"))
        
        # Extract content
        content = result.get("content", {})
        formatted = format_product_output(content)
        return formatted
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in products endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error finding products: {str(e)}")


@router.post("/recipes")
async def recipes_endpoint(request: RecipeRequest):
    """Find recipes using Perplexity API."""
    try:
        from services.perplexity_service import PerplexityService
        
        # Build search query
        search_query = request.search_query or request.prompt or "recipes"
        
        # Initialize Perplexity service
        perplexity = PerplexityService()
        
        # Search for recipes
        result = await perplexity.search_recipes(
            query=search_query,
            cuisine_type=request.cuisine_type,
            diet=request.diet,
            nutrition_requirements=request.nutrition_requirements,
            max_results=request.max_results or 5
        )
        
        # Format response
        return {
            "success": True,
            "recipes": result.get("recipes", []),
            "content": result.get("content", ""),
            "citations": result.get("citations", []),
            "count": len(result.get("recipes", []))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in recipes endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error finding recipes: {str(e)}")


@router.post("/goal-impact", response_model=GoalImpactResponse)
async def goal_impact_endpoint(request: GoalImpactRequest):
    """Analyze the impact of actual meal consumption on daily nutrition goals.
    
    This endpoint helps users understand how their actual consumption deviates from
    their planned meals and provides suggestions to get back on track.
    
    Example:
        Daily goal: 1200 calories in 3 meals
        Planned breakfast: 300 calories
        Actual breakfast: 600 calories
        -> Analyzes impact and suggests adjustments for remaining meals
    """
    try:
        from services.goal_impact_service import GoalImpactService
        
        # Convert Pydantic models to dictionaries
        daily_goal_dict = {
            "calories": request.daily_goal.calories,
            "protein": request.daily_goal.protein,
            "carbs": request.daily_goal.carbs,
            "fats": request.daily_goal.fats,
            "fiber": request.daily_goal.fiber,
        }
        # Remove None values
        daily_goal_dict = {k: v for k, v in daily_goal_dict.items() if v is not None}
        
        consumed_meals_list = []
        for meal in request.consumed_meals:
            consumed_meals_list.append({
                "meal_type": meal.meal_type,
                "planned_nutrition": meal.planned_nutrition,
                "actual_nutrition": meal.actual_nutrition
            })
        
        remaining_meals_list = None
        if request.remaining_meals:
            remaining_meals_list = request.remaining_meals
        
        # Initialize goal impact service
        goal_impact_service = GoalImpactService()
        
        # Analyze impact
        result = await goal_impact_service.analyze_goal_impact(
            daily_goal=daily_goal_dict,
            meals_per_day=request.meals_per_day,
            consumed_meals=consumed_meals_list,
            remaining_meals=remaining_meals_list
        )
        
        # Validate and return response
        return GoalImpactResponse(
            impact_analysis=result.get("impact_analysis", {}),
            current_status=result.get("current_status", {}),
            suggestions=result.get("suggestions", []),
            adjusted_plan=result.get("adjusted_plan"),
            severity=result.get("severity", "medium")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in goal impact endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing goal impact: {str(e)}"
        )


@router.post("/meal-nutrition", response_model=MealNutritionResponse)
async def meal_nutrition_endpoint(request: MealNutritionRequest):
    """Find nutritional content for a meal from its description.
    
    This endpoint helps users find nutrition information (calories, protein, carbs, fats, etc.)
    for meals described in natural language.
    
    Example:
        Input: "I ate pavbhaji instead of 1 bowl of oatmeal today"
        -> Returns nutrition information for pavbhaji
        
        Input: "2 slices of pizza"
        -> Returns nutrition for 2 slices of pizza
    """
    try:
        from services.meal_nutrition_service import MealNutritionService
        
        # Initialize meal nutrition service
        meal_nutrition_service = MealNutritionService()
        
        # Find nutrition
        result = await meal_nutrition_service.find_meal_nutrition(
            meal_description=request.meal_description,
            serving_size=request.serving_size,
            cuisine_type=request.cuisine_type
        )
        
        # Return response
        return MealNutritionResponse(
            meal_name=result.get("meal_name", request.meal_description),
            serving_size=result.get("serving_size"),
            nutrition=result.get("nutrition", {}),
            confidence=result.get("confidence", "low"),
            source=result.get("source"),
            notes=result.get("notes")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in meal nutrition endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error finding meal nutrition: {str(e)}"
        )

