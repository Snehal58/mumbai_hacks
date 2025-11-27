"""REST API routes (optional, for non-WebSocket endpoints)."""

from typing import Any, Callable, Dict, Optional, Tuple, Type
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from models.schemas import (
    WebSocketMessage,
    PlannerRequest,
    RestaurantRequest,
    ProductRequest
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
    format_restaurant_output,
    format_product_output
)
from utils.logger import setup_logger
import json
import uuid

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])


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

