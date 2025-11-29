"""Diet API routes."""

from fastapi import APIRouter, HTTPException, Query
from typing import List
from models.database import get_diet_collection
from schemas.diet_collection import DietCollection
from utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["diet"])


@router.get("/diet", response_model=dict)
async def get_diet_by_user_id(user_id: str = Query(..., description="User identifier")):
    """Get meal plan from diet_collection based on user_id using DietCollection schema.
    
    Returns all diet entries (meals) for the specified user in DietCollection format.
    """
    try:
        diet_collection = get_diet_collection()
        
        # Find all diet entries for the user, sorted by meal_no
        cursor = diet_collection.find({"user_id": user_id}).sort("meal_no", 1)
        diet_entries = await cursor.to_list(length=None)
        
        # Convert ObjectId to string for JSON serialization and validate with DietCollection schema
        validated_entries = []
        for entry in diet_entries:
            if "_id" in entry:
                entry["_id"] = str(entry["_id"])
            # Validate entry against DietCollection schema
            try:
                validated_entry = DietCollection(**entry)
                validated_entries.append(validated_entry.model_dump())
            except Exception as e:
                logger.warning(f"Invalid diet entry format: {e}, entry: {entry}")
                # Include anyway but log warning
                validated_entries.append(entry)
        
        if not validated_entries:
            logger.info(f"No diet entries found for user_id: {user_id}")
            return {
                "user_id": user_id,
                "diet_entries": [],
                "count": 0
            }
        
        logger.info(f"Retrieved {len(validated_entries)} diet entries for user_id: {user_id}")
        return {
            "user_id": user_id,
            "diet_entries": validated_entries,
            "count": len(validated_entries)
        }
        
    except Exception as e:
        logger.error(f"Error fetching diet for user_id {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching diet: {str(e)}")

