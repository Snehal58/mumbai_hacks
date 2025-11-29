"""Planner-related tools."""

from langchain.tools import tool
from datetime import datetime
import json
from models.database import get_sync_diet_collection, get_sync_diet_logs_collection
from utils.logger import setup_logger

logger = setup_logger(__name__)


@tool
def get_meal_plan(user_id: str) -> str:
    """Get all meals for a user from the diet collection.
    
    Queries the diet collection for all meals associated with the given user_id.
    Returns all meals ordered by meal_no.
    
    Args:
        user_id: User identifier
        
    Returns:
        JSON string with list of meal documents, or empty list if no meals found
    """
    try:
        diet_collection = get_sync_diet_collection()
        
        # Find all meals for the user, ordered by meal_no
        meals = list(diet_collection.find({
            "user_id": user_id
        }).sort("meal_no", 1))
        
        if meals:
            # Convert ObjectId to string for JSON serialization
            for meal in meals:
                if "_id" in meal:
                    meal["_id"] = str(meal["_id"])
            return json.dumps(meals, default=str)
        else:
            return json.dumps([])
            
    except Exception as e:
        logger.error(f"Error getting meal plan: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool
def upsert_meal_plan(user_id: str, meals: str) -> str:
    """Upsert (insert or update) meal documents in the diet collection.
    
    Upserts multiple meals for a user. Each meal should have meal_no and data fields.
    The data field contains the meal information to upsert.
    
    Args:
        user_id: User identifier
        meals: JSON string containing a list of meal objects with structure:
            [
                {
                    "meal_no": int,
                    "data": {
                        "meal_time": str,
                        "meal_description": str,
                        "meal_nutrient": {
                            "name": str,
                            "qty": float,
                            "unit": str
                        }
                    }
                }
            ]
        
    Returns:
        JSON string with success message and number of meals upserted
    """
    try:
        diet_collection = get_sync_diet_collection()
        
        # Parse meals JSON string
        meals_list = json.loads(meals) if isinstance(meals, str) else meals
        
        if not isinstance(meals_list, list):
            return json.dumps({"error": "meals must be a list", "success": False})
        
        upserted_count = 0
        
        # Upsert each meal
        for meal_item in meals_list:
            if not isinstance(meal_item, dict):
                continue
                
            meal_no = meal_item.get("meal_no")
            meal_data = meal_item.get("data", {})
            
            if meal_no is None:
                continue
            
            # Ensure user_id and meal_no are set
            meal_data["user_id"] = user_id
            meal_data["meal_no"] = meal_no
            
            # Upsert the meal
            result = diet_collection.update_one(
                {"user_id": user_id, "meal_no": meal_no},
                {"$set": meal_data},
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                upserted_count += 1
        
        logger.info(f"Upserted {upserted_count} meals for user {user_id}")
        
        return json.dumps({
            "success": True,
            "message": f"Successfully upserted {upserted_count} meal(s)",
            "upserted_count": upserted_count,
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Error upserting meal plan: {e}", exc_info=True)
        return json.dumps({"error": str(e), "success": False})


@tool
def log_diet(user_id: str, date: str, data: str) -> str:
    """Log a consumed meal in the diet_logs collection.
    
    Inserts a diet log document when a user consumes a meal.
    This is used to track meal consumption history.
    
    Args:
        user_id: User identifier
        date: Date in ISO format (YYYY-MM-DD) or datetime string
        data: JSON string containing diet log data with fields:
            - meal_name: Name of the meal (e.g., "Pizza", "Chicken Salad")
            - meal_time: Time of the meal (e.g., "12:00 PM", "8:00 AM")
            - meal_description: Description of what was consumed
            - meal_nutrients: Dictionary of nutrient values (e.g., {{"calories": 500.0, "protein": 25.0, "carbs": 60.0, "fat": 20.0}})
        
    Returns:
        JSON string with success message and log_id
    """
    try:
        diet_logs_collection = get_sync_diet_logs_collection()
        
        # Parse date string
        if isinstance(date, str):
            try:
                # Try parsing ISO format
                date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Try parsing common formats
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                except (ValueError, TypeError):
                    date_obj = datetime.utcnow()
        else:
            date_obj = date if isinstance(date, datetime) else datetime.utcnow()
        
        # Normalize date to start of day (midnight) for consistent matching
        date_obj = datetime.combine(date_obj.date(), datetime.min.time())
        
        # Parse data JSON string
        log_data = json.loads(data) if isinstance(data, str) else data
        
        # Ensure user_id and date are set
        log_data["user_id"] = user_id
        log_data["date"] = date_obj
        
        # Ensure required fields are present with defaults
        if "meal_name" not in log_data:
            log_data["meal_name"] = "Meal"
        if "meal_time" not in log_data:
            # Default to current time if not provided
            current_time = datetime.utcnow()
            log_data["meal_time"] = current_time.strftime("%I:%M %p")
        if "meal_description" not in log_data:
            log_data["meal_description"] = log_data.get("meal_name", "Meal consumed")
        if "meal_nutrients" not in log_data:
            log_data["meal_nutrients"] = {}
        
        # Insert the diet log using synchronous PyMongo operations
        result = diet_logs_collection.insert_one(log_data)
        
        logger.info(f"Logged diet for user {user_id} on date {date}")
        
        return json.dumps({
            "success": True,
            "message": "Meal logged successfully",
            "user_id": user_id,
            "date": date_obj.isoformat() if isinstance(date_obj, datetime) else str(date_obj),
            "log_id": str(result.inserted_id)
        })
        
    except Exception as e:
        logger.error(f"Error logging diet: {e}", exc_info=True)
        return json.dumps({"error": str(e), "success": False})