"""Goal-related tools for the goal journey agent."""

from langchain.tools import tool
from datetime import datetime
import asyncio
import json
from models.database import get_goal_collection
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Apply nest_asyncio at module level to allow nested event loops
try:
    import nest_asyncio  # type: ignore
    nest_asyncio.apply()
except ImportError:
    pass  # nest_asyncio not available, will use thread executor fallback


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
def get_active_user_goal(user_id: str, current_date: str) -> str:
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
        
        goal_collection = get_goal_collection()
        
        # Parse current_date if it's a string
        if isinstance(current_date, str):
            try:
                # Try parsing ISO format
                current_dt = dt.fromisoformat(current_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Try parsing common formats
                try:
                    current_dt = dt.strptime(current_date, "%Y-%m-%d")
                except (ValueError, TypeError):
                    current_dt = dt.utcnow()
        else:
            current_dt = current_date if isinstance(current_date, datetime) else dt.utcnow()
        
        # Find goal where user_id matches and end_date > current_date
        # Note: This is a synchronous wrapper - MongoDB operations are async
        async def _find_goal():
            return await goal_collection.find_one({
                "user_id": user_id,
                "end_date": {"$gt": current_dt}
            })
        
        goal = _run_async(_find_goal())
        
        if goal:
            # Convert ObjectId to string for JSON serialization
            goal["_id"] = str(goal["_id"])
            # Convert datetime objects to ISO strings
            if "start_date" in goal and isinstance(goal["start_date"], datetime):
                goal["start_date"] = goal["start_date"].isoformat()
            if "end_date" in goal and isinstance(goal["end_date"], datetime):
                goal["end_date"] = goal["end_date"].isoformat()
            return json.dumps(goal, default=str)
        else:
            return json.dumps({})
            
    except Exception as e:
        logger.error(f"Error getting active user goal: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool
def upsert_goal(user_id: str, goal_id: str, data: str) -> str:
    """Upsert (insert or update) a goal document.
    
    Upserts a goal document using user_id and goal_id as the filter.
    If a goal with the same user_id and goal_id exists, it will be updated.
    Otherwise, a new goal will be created.
    
    Args:
        user_id: User identifier
        goal_id: Goal identifier (unique per user)
        data: JSON string containing goal data with fields:
            - goal_name: Name of the goal
            - start_date: Start date (ISO format)
            - end_date: End date (ISO format)
            - target_weight: Target weight in kg
            - workout_skipped: Number of workouts skipped (default: 0)
            - cheat_meals: Number of cheat meals (default: 0)
            - extra_workouts: Number of extra workouts (default: 0)
            - avg_daily_burn: Average daily calories burned (default: 0.0)
            - avg_consumption: Average daily calories consumed (default: 0.0)
            - avg_protein: Average daily protein intake in grams (default: 0.0)
            - consistency_percentage: Consistency percentage (default: 0.0)
        
    Returns:
        JSON string with success message and goal_id
    """
    try:
        from datetime import datetime as dt
        
        goal_collection = get_goal_collection()
        
        # Parse data JSON string
        goal_data = json.loads(data) if isinstance(data, str) else data
        
        # Ensure user_id and goal_id are set
        goal_data["user_id"] = user_id
        goal_data["goal_id"] = goal_id
        
        # Parse datetime strings if present
        if "start_date" in goal_data and isinstance(goal_data["start_date"], str):
            goal_data["start_date"] = dt.fromisoformat(goal_data["start_date"].replace('Z', '+00:00'))
        if "end_date" in goal_data and isinstance(goal_data["end_date"], str):
            goal_data["end_date"] = dt.fromisoformat(goal_data["end_date"].replace('Z', '+00:00'))
        
        # Set defaults for optional fields
        defaults = {
            "workout_skipped": 0,
            "cheat_meals": 0,
            "extra_workouts": 0,
            "avg_daily_burn": 0.0,
            "avg_consumption": 0.0,
            "avg_protein": 0.0,
            "consistency_percentage": 0.0
        }
        for key, value in defaults.items():
            if key not in goal_data:
                goal_data[key] = value
        
        # Upsert the goal
        # Note: This is a synchronous wrapper - MongoDB operations are async
        async def _upsert_goal():
            return await goal_collection.update_one(
                {"user_id": user_id, "goal_id": goal_id},
                {"$set": goal_data},
                upsert=True
            )
        
        result = _run_async(_upsert_goal())
        
        if result.upserted_id:
            logger.info(f"Created new goal for user {user_id} with goal_id {goal_id}")
        else:
            logger.info(f"Updated existing goal for user {user_id} with goal_id {goal_id}")
        
        return json.dumps({
            "success": True,
            "message": "Goal saved successfully",
            "goal_id": goal_id,
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Error upserting goal: {e}", exc_info=True)
        return json.dumps({"error": str(e), "success": False})

