"""Goal routes for goal management."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from models.database import get_goal_collection
from schemas.goal_collection import GoalCollection
from utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


@router.get("/active", response_model=GoalCollection)
async def get_active_goal(
    user_id: str = Query(..., description="User identifier")
):
    """
    Get the active goal for a user.
    Returns the goal document where end_date is greater than current date.
    """
    try:
        goal_collection = get_goal_collection()
        
        # Get current date
        current_date = datetime.utcnow()
        
        # Find goal where user_id matches and end_date > current_date
        goal = await goal_collection.find_one({
            "user_id": user_id,
            "end_date": {"$gt": current_date}
        }, sort=[("start_date", -1)])  # Sort by start_date descending to get most recent
        
        if not goal:
            raise HTTPException(
                status_code=404,
                detail=f"No active goal found for user_id '{user_id}'"
            )
        
        # Convert MongoDB document to Pydantic model
        goal["_id"] = str(goal["_id"])  # Convert ObjectId to string
        
        return GoalCollection(**goal)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching active goal: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching active goal: {str(e)}"
        )


@router.post("/", response_model=GoalCollection)
async def create_goal(goal: GoalCollection):
    """Create a new goal."""
    try:
        goal_collection = get_goal_collection()
        
        # Convert Pydantic model to dict
        goal_dict = goal.model_dump()
        
        # Insert the goal
        result = await goal_collection.insert_one(goal_dict)
        
        # Get the created goal
        created_goal = await goal_collection.find_one({"_id": result.inserted_id})
        created_goal["_id"] = str(created_goal["_id"])
        
        return GoalCollection(**created_goal)
    
    except Exception as e:
        logger.error(f"Error creating goal: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating goal: {str(e)}"
        )

