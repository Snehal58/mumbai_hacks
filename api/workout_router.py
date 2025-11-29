# from fastapi import APIRouter

# router = APIRouter(prefix="/api/v1/workout", tags=["api"])

# Get workout details by user id for today - Return non expired workouts
# Get workout by user id - Return non temp workout
# Upsert workout by user id
# Is workout created - If no data found for a particular user_id return false else return true

from fastapi import APIRouter
from datetime import datetime, timedelta
from models.database import get_database
from utils.logger import setup_logger

router = APIRouter(prefix="/api/v1/workout", tags=["api"])

logger = setup_logger(__name__)

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