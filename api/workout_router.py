# from fastapi import APIRouter

# router = APIRouter(prefix="/api/v1/workout", tags=["api"])

# Get workout details by user id for today - Return non expired workouts
# Get workout by user id - Return non temp workout
# Upsert workout by user id
# Is workout created - If no data found for a particular user_id return false else return true
import json
import uuid

from fastapi import APIRouter, WebSocket
from datetime import datetime, timedelta
from models.database import get_database
from prompts.workout_agent_prompt import WORKOUT_AGENT_PROMPT
from schemas.workout import Workout
from services.llm_factory import get_llm
from services.workflow import stream_workout_agent
from utils.logger import setup_logger
from fastapi import WebSocketDisconnect
from langgraph.prebuilt import create_react_agent

router = APIRouter(prefix="/api/v1/workout", tags=["api"])

logger = setup_logger(__name__)

planner_llm = get_llm("planner_agent")

planner_agent = create_react_agent(
    model=planner_llm,
    tools=[],
    name="planner_agent",
    prompt=WORKOUT_AGENT_PROMPT.template,
)

# ---------------------------
# Helpers
# ---------------------------

def workout_serializer(workout):
    """Serialize MongoDB workout document."""
    if not workout:
        return None
    workout["_id"] = str(workout["_id"])
    return workout

# ---------------------------
# 1. Get today's workout for user (non-expired)
# ---------------------------

@router.get("/today/{user_id}")
async def get_today_workout(user_id: str):
    """
    Return today’s non-expired workout for a user.
    Expiry must be >= now and date must match today.
    """
    db = get_database()

    today = datetime.utcnow().date()

    workout = await db.workouts.find_one({
        "user_id": user_id,
        "is_temp": False,
        "$expr": { "$eq": [{ "$dateToString": { "format": "%Y-%m-%d", "date": "$date" } }, str(today)] },
        "expiry": { "$gte": datetime.utcnow() }
    })

    if not workout:
        return {"found": False, "data": None}

    return {"found": True, "data": workout_serializer(workout)}

# ---------------------------
# 2. Get user workout (non-temp)
# ---------------------------

@router.get("/week/{user_id}")
async def get_user_workout(user_id: str):
    """
    Get all non-temp workouts for the user between today and the last 7 days.
    """
    db = get_database()

    today = datetime.utcnow().date()
    today_str = today.strftime("%Y-%m-%d")

    # 7 days ago
    week_later = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    cursor = db.workouts.find(
        {
            "user_id": user_id,
            "is_temp": False,
            "date_str": {"$gte": today_str, "$lte": week_later}
        }
    ).sort("date", -1)

    workouts = await cursor.to_list(length=None)

    if not workouts:
        return {"found": False, "data": []}

    return {
        "found": True,
        "count": len(workouts),
        "data": [workout_serializer(w) for w in workouts]
    }

# ---------------------------
# 3. Upsert workout (for today)
# ---------------------------

@router.post("/upsert")
async def upsert_workout(payload: Workout):
    """
    Insert or update a workout for the given user & date.
    If workout exists for today → update it.
    Otherwise → insert new workout.
    """
    db = get_database()

    # Normalize date to YYYY-MM-DD
    normalized_date = payload.date.strftime("%Y-%m-%d")

    # Filter by user_id + normalized date (no $expr)
    filter_query = {
        "user_id": payload.user_id,
        "date_str": normalized_date
    }

    # Ensure date_str is stored in the document
    update_doc = {
        "$set": {
            **payload.model_dump(),
            "date_str": normalized_date
        }
    }

    updated = await db.workouts.update_one(filter_query, update_doc, upsert=True)

    return {
        "updated": updated.modified_count > 0,
        "inserted": updated.upserted_id is not None,
        "id": str(updated.upserted_id) if updated.upserted_id else None
    }

# ---------------------------
# 4. Check if workout exists for a user
# ---------------------------

@router.get("/is-created/{user_id}")
async def is_workout_created(user_id: str):
    """
    Returns true if any workout exists for user_id.
    """
    db = get_database()

    workout = await db.workouts.find_one({"user_id": user_id})

    return {"created": workout is not None}

@router.websocket("/stream/{user_id}")
async def workout_stream(websocket: WebSocket, user_id: str):
    """Handle WebSocket connection for planner agent streaming."""
    session_id = str(uuid.uuid4())
    
    try:
        await websocket.accept()
        logger.info(f"Workout WebSocket connected: {session_id}")
        
        # Send connection confirmation
        await websocket.send_json({
            "event": "connected",
            "data": {"message": "Connected to workout stream", "session_id": session_id},
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
            
            logger.info(f"Received workout request for session {session_id}, prompt length: {len(prompt)}")
            
            # Stream planner agent events
            async for event in stream_workout_agent(prompt=prompt, session_id=session_id, user_id=user_id):
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
        

