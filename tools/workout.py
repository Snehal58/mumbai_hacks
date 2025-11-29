"""Workout-related tools for the workout agent."""

from langchain.tools import tool
from datetime import datetime, timedelta
import json
from models.database import get_sync_workout_collection, get_sync_workout_logs_collection
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _get_week_start_end(date_str: str):
    """Get the start (Monday) and end (Sunday) of the week for a given date.
    
    Args:
        date_str: Date string in ISO format (YYYY-MM-DD) or datetime string
        
    Returns:
        Tuple of (week_start, week_end) as datetime objects
    """
    from datetime import datetime as dt
    
    # Parse date string
    if isinstance(date_str, str):
        try:
            # Try parsing ISO format
            date_obj = dt.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            # Try parsing common formats
            try:
                date_obj = dt.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                date_obj = dt.utcnow()
    else:
        date_obj = date_str if isinstance(date_str, datetime) else dt.utcnow()
    
    # Get the date part (remove time)
    date_only = date_obj.date() if isinstance(date_obj, datetime) else date_obj
    
    # Calculate Monday of the week (weekday() returns 0 for Monday, 6 for Sunday)
    days_since_monday = date_only.weekday()
    week_start = datetime.combine(date_only - timedelta(days=days_since_monday), datetime.min.time())
    
    # Calculate Sunday of the week
    week_end = datetime.combine(week_start.date() + timedelta(days=6), datetime.max.time())
    
    return week_start, week_end


@tool
def get_active_workout(user_id: str, date: str) -> str:
    """Get all workouts for a user in the week that contains the given date.
    
    Queries the workout collection for all workouts where user_id matches 
    and the workout date falls within the week (Monday to Sunday) that contains 
    the given date.
    
    Args:
        user_id: User identifier
        date: Date in ISO format (YYYY-MM-DD) or datetime string
        
    Returns:
        JSON string with list of workout documents found, or empty list if none found
    """
    try:
        workout_collection = get_sync_workout_collection()
        
        # Get week start and end dates
        week_start, week_end = _get_week_start_end(date)
        
        # Find all workouts for the user in this week
        workouts = list(workout_collection.find({
            "user_id": user_id,
            "date": {
                "$gte": week_start,
                "$lte": week_end
            },
            "is_temp": False
        }).sort("date", 1))
        
        # Serialize workouts
        serialized_workouts = []
        for workout in workouts:
            if "_id" in workout:
                workout["_id"] = str(workout["_id"])
            # Convert datetime objects to ISO strings
            if "date" in workout and isinstance(workout["date"], datetime):
                workout["date"] = workout["date"].isoformat()
            if "expiry" in workout and isinstance(workout["expiry"], datetime):
                workout["expiry"] = workout["expiry"].isoformat()
            serialized_workouts.append(workout)
        
        return json.dumps(serialized_workouts, default=str)
            
    except Exception as e:
        logger.error(f"Error getting active workouts: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool
def upsert_workout(user_id: str, date: str, data: str) -> str:
    """Upsert (insert or update) a workout document.
    
    Upserts a workout document using user_id and date as the filter.
    If a workout with the same user_id and date exists, it will be updated.
    Otherwise, a new workout will be created.
    
    Args:
        user_id: User identifier
        date: Date in ISO format (YYYY-MM-DD) or datetime string
        data: JSON string containing workout data with fields:
            - type: Workout type (upper, lower, or full body)
            - repetitions: Number of repetitions (default: 0)
            - expiry: Validity of the workout (datetime, optional)
            - plan: List of plan items with name and sets (default: [])
            - is_temp: Whether the workout is temporary (default: False)
        
    Returns:
        JSON string with success message
    """
    try:
        from datetime import datetime as dt
        
        workout_collection = get_sync_workout_collection()
        
        # Parse date string
        if isinstance(date, str):
            try:
                # Try parsing ISO format
                date_obj = dt.fromisoformat(date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Try parsing common formats
                try:
                    date_obj = dt.strptime(date, "%Y-%m-%d")
                except (ValueError, TypeError):
                    date_obj = dt.utcnow()
        else:
            date_obj = date if isinstance(date, datetime) else dt.utcnow()
        
        # Normalize date to start of day (midnight) for consistent matching
        date_obj = dt.combine(date_obj.date(), dt.min.time())
        
        # Parse data JSON string
        workout_data = json.loads(data) if isinstance(data, str) else data
        
        # Ensure user_id and date are set
        workout_data["user_id"] = user_id
        workout_data["date"] = date_obj
        
        # Parse datetime strings if present
        if "expiry" in workout_data and isinstance(workout_data["expiry"], str):
            workout_data["expiry"] = dt.fromisoformat(workout_data["expiry"].replace('Z', '+00:00'))
        
        # Set defaults for optional fields
        defaults = {
            "type": "upper",
            "repetitions": 0,
            "expiry": None,
            "plan": [],
            "is_temp": False
        }
        for key, value in defaults.items():
            if key not in workout_data:
                workout_data[key] = value
        
        # Upsert the workout using synchronous PyMongo operations
        result = workout_collection.update_one(
            {"user_id": user_id, "date": date_obj},
            {"$set": workout_data},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"Created new workout for user {user_id} on date {date}")
        else:
            logger.info(f"Updated existing workout for user {user_id} on date {date}")
        
        return json.dumps({
            "success": True,
            "message": "Workout saved successfully",
            "user_id": user_id,
            "date": date_obj.isoformat() if isinstance(date_obj, datetime) else str(date_obj)
        })
        
    except Exception as e:
        logger.error(f"Error upserting workout: {e}", exc_info=True)
        return json.dumps({"error": str(e), "success": False})


@tool
def log_workout(user_id: str, date: str, data: str) -> str:
    """Log a completed workout in the workout_logs collection.
    
    Inserts a workout log document when a user completes a workout.
    This is used to track workout completion history.
    
    Args:
        user_id: User identifier
        date: Date in ISO format (YYYY-MM-DD) or datetime string
        data: JSON string containing workout log data with fields:
            - type: Workout type (e.g., "upper", "lower", "full body")
            - plan: Workout plan description or exercises performed (string)
            - is_extra: Whether this is an extra workout beyond the planned schedule (default: False)
        
    Returns:
        JSON string with success message and log_id
    """
    try:
        from datetime import datetime as dt
        
        workout_logs_collection = get_sync_workout_logs_collection()
        
        # Parse date string
        if isinstance(date, str):
            try:
                # Try parsing ISO format
                date_obj = dt.fromisoformat(date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Try parsing common formats
                try:
                    date_obj = dt.strptime(date, "%Y-%m-%d")
                except (ValueError, TypeError):
                    date_obj = dt.utcnow()
        else:
            date_obj = date if isinstance(date, datetime) else dt.utcnow()
        
        # Normalize date to start of day (midnight) for consistent matching
        date_obj = dt.combine(date_obj.date(), dt.min.time())
        
        # Parse data JSON string
        log_data = json.loads(data) if isinstance(data, str) else data
        
        # Ensure user_id and date are set
        log_data["user_id"] = user_id
        log_data["date"] = date_obj
        
        # Set defaults for optional fields
        defaults = {
            "is_extra": False
        }
        for key, value in defaults.items():
            if key not in log_data:
                log_data[key] = value
        
        # Ensure required fields are present
        if "type" not in log_data:
            log_data["type"] = "general"
        if "plan" not in log_data:
            log_data["plan"] = "Workout completed"
        
        # Insert the workout log using synchronous PyMongo operations
        result = workout_logs_collection.insert_one(log_data)
        
        logger.info(f"Logged workout for user {user_id} on date {date}")
        
        return json.dumps({
            "success": True,
            "message": "Workout logged successfully",
            "user_id": user_id,
            "date": date_obj.isoformat() if isinstance(date_obj, datetime) else str(date_obj),
            "log_id": str(result.inserted_id)
        })
        
    except Exception as e:
        logger.error(f"Error logging workout: {e}", exc_info=True)
        return json.dumps({"error": str(e), "success": False})
