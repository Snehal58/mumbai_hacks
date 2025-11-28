"""Database models and connection setup."""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from typing import Optional
from config.settings import settings
from urllib.parse import urlparse


class Database:
    """Database connection manager."""
    
    client: Optional[AsyncIOMotorClient] = None


db = Database()


async def connect_to_mongo():
    """Create database connection."""
    db.client = AsyncIOMotorClient(settings.mongodb_url)
    print(f"Connected to MongoDB: {settings.mongodb_url}")


async def close_mongo_connection():
    """Close database connection."""
    if db.client:
        db.client.close()
        print("Disconnected from MongoDB")




async def init_mongo():
    """Initialize MongoDB connection and all collections with indexes."""
    # Connect to MongoDB
    await connect_to_mongo()
    
    # Initialize all collections
    database = get_database()
    
    # Users collection
    users_collection = database.users
    await users_collection.create_index([("user_id", ASCENDING)], unique=True)
    
    # Workout collection
    workout_collection = database.workout
    await workout_collection.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
    await workout_collection.create_index([("date", DESCENDING)])
    
    # Workout logs collection
    workout_logs_collection = database.workout_logs
    await workout_logs_collection.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
    await workout_logs_collection.create_index([("date", DESCENDING)])
    
    # Diet logs collection
    diet_logs_collection = database.diet_logs
    await diet_logs_collection.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
    await diet_logs_collection.create_index([("date", DESCENDING)])
    
    # Diet collection
    diet_collection = database.diet_collection
    await diet_collection.create_index([("user_id", ASCENDING), ("meal_no", ASCENDING)])
    
    # Goal collection
    goal_collection = database.goal_collection
    await goal_collection.create_index([("user_id", ASCENDING), ("start_date", DESCENDING)])
    await goal_collection.create_index([("user_id", ASCENDING)])
    
    # Checkpoint collection
    checkpoint_collection = database.checkpoints
    await checkpoint_collection.create_index([("session_id", ASCENDING)], unique=True)
    await checkpoint_collection.create_index([("last_updated", DESCENDING)])
    
    print("MongoDB initialized: All collections created with indexes")


def get_database():
    """Get database instance."""
    # Parse the MongoDB URL to extract database name
    parsed_url = urlparse(settings.mongodb_url)
    # Database name is the last part of the path, or default to 'meal_planner'
    db_name = parsed_url.path.strip('/').split('/')[-1] if parsed_url.path else 'meal_planner'
    return db.client[db_name]


# Helper functions to get collections
def get_users_collection():
    """Get users collection."""
    return get_database().users


def get_workout_collection():
    """Get workout collection."""
    return get_database().workout


def get_workout_logs_collection():
    """Get workout logs collection."""
    return get_database().workout_logs


def get_diet_logs_collection():
    """Get diet logs collection."""
    return get_database().diet_logs


def get_diet_collection():
    """Get diet collection."""
    return get_database().diet_collection


def get_goal_collection():
    """Get goal collection."""
    return get_database().goal_collection


def get_checkpoints_collection():
    """Get checkpoints collection."""
    return get_database().checkpoints

