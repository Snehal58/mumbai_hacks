"""Diet API routes."""

from fastapi import APIRouter, HTTPException, Query
from models.database import get_diet_collection
from utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["diet"])


@router.get("/diet")
async def get_diet_by_user_id(user_id: str = Query(..., description="User identifier")):
    """Get diet information from diet_collection based on user_id.
    
    Returns all diet entries (meals) for the specified user.
    """
    try:
        diet_collection = get_diet_collection()
        
        # Find all diet entries for the user
        cursor = diet_collection.find({"user_id": user_id})
        diet_entries = await cursor.to_list(length=None)
        
        # Convert ObjectId to string for JSON serialization
        for entry in diet_entries:
            if "_id" in entry:
                entry["_id"] = str(entry["_id"])
        
        if not diet_entries:
            logger.info(f"No diet entries found for user_id: {user_id}")
            return {
                "user_id": user_id,
                "diet_entries": [],
                "count": 0
            }
        
        logger.info(f"Retrieved {len(diet_entries)} diet entries for user_id: {user_id}")
        return {
            "user_id": user_id,
            "diet_entries": diet_entries,
            "count": len(diet_entries)
        }
        
    except Exception as e:
        logger.error(f"Error fetching diet for user_id {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching diet: {str(e)}")

