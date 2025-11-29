"""Goal-related tools for the goal journey agent."""

from langchain.tools import tool
from datetime import datetime
import asyncio
import json
from models.database import get_sync_database
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Apply nest_asyncio at module level to allow nested event loops
try:
    import nest_asyncio  # type: ignore
    nest_asyncio.apply()
except ImportError:
    pass  # nest_asyncio not available, will use thread executor fallback

def _upsert_workout_tool(payload):
        db = get_sync_database()

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

        updated = db.workouts.update_one(filter_query, update_doc, upsert=True)

        return {
            "updated": updated.modified_count > 0,
            "inserted": updated.upserted_id is not None,
            "id": str(updated.upserted_id) if updated.upserted_id else None
        }

def _run_async(coro):
    """Helper to run async function synchronously."""
    try:
        # Check if we're in an async context
        asyncio.get_running_loop()
        # If we're here, we're in an async context
        # Use nest_asyncio if available to allow nested event loops
        try:
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
            # Now we can use asyncio.run even though there's a running loop
            return asyncio.run(coro)
        except ImportError:
            # Fallback: create a new event loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
    except RuntimeError:
        # No event loop running, create a new one
        return asyncio.run(coro)


@tool
def get_active_workout(user_id: str, current_date: str):
    """Get the active goal for a user.
    
    Queries the goal collection for an active goal where user_id matches 
    and end_date is greater than current_date.
    
    Args:
        user_id: User identifier
        current_date: Current date in ISO format (YYYY-MM-DD) or datetime string
        
    Returns:
        JSON string with goal document if found, or empty dict if not found
    """
    try:
        db = get_sync_database()

        today = datetime.utcnow().date()
        
        def workout_serializer(workout):
            """Serialize MongoDB workout document."""
            if not workout:
                return None
            workout["_id"] = str(workout["_id"])
            return workout

        workout = db.workouts.find_one({
            "user_id": user_id,
            "is_temp": False,
            "$expr": { "$eq": [{ "$dateToString": { "format": "%Y-%m-%d", "date": "$date" } }, str(today)] },
            "expiry": { "$gte": datetime.utcnow() }
        })

        if not workout:
            return {"found": False, "data": None}

        return {"found": True, "data": workout_serializer(workout)}
            
    except Exception as e:
        logger.error(f"Error getting active user goal: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool
def upsert_workout_tool(user_id: str, goal_id: str, data: str):
    """Get the active goal for a user.
    
    Queries the goal collection for an active goal where user_id matches 
    and end_date is greater than current_date.
    
    Args:
        user_id: User identifier
        current_date: Current date in ISO format (YYYY-MM-DD) or datetime string
        
    Returns:
        JSON string with goal document if found, or empty dict if not found
    """
    try:
        from datetime import datetime as dt
        
        # Parse data JSON string
        goal_data = json.loads(data) if isinstance(data, str) else data
        
        # Ensure user_id and goal_id are set
        goal_data["user_id"] = user_id
        
        # Parse datetime strings if present
        # if "start_date" in goal_data and isinstance(goal_data["start_date"], str):
        #     goal_data["start_date"] = dt.fromisoformat(goal_data["start_date"].replace('Z', '+00:00'))
        # if "end_date" in goal_data and isinstance(goal_data["end_date"], str):
        #     goal_data["end_date"] = dt.fromisoformat(goal_data["end_date"].replace('Z', '+00:00'))
        
        # Set defaults for optional fields
        defaults = {
            "type": "upper",
            # 
            "repetitions": 0,
            "expiry": None,
            "plan": [],
            "is_temp": False
        }
        for key, value in defaults.items():
            if key not in goal_data:
                goal_data[key] = value
        
        # Upsert the goal
        # Note: This is a synchronous wrapper - MongoDB operations are async
        async def _upsert_workout():
            return _upsert_workout_tool(goal_data)
        
        _run_async(_upsert_workout())
        
        # if result.upserted_id:
        #     logger.info(f"Created new goal for user {user_id} with goal_id {goal_id}")
        # else:
        #     logger.info(f"Updated existing goal for user {user_id} with goal_id {goal_id}")
        
        # return json.dumps({
        #     "success": True,
        #     "message": "Goal saved successfully",
        #     "goal_id": goal_id,
        #     "user_id": user_id
        # })
    
        
    except Exception as e:
        logger.error(f"Error upserting goal: {e}", exc_info=True)
        return json.dumps({"error": str(e), "success": False})

