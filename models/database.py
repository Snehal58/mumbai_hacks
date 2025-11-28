"""Database models and connection setup."""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ASCENDING, DESCENDING
from typing import Optional
from config.settings import settings
import redis.asyncio as aioredis


class Database:
    """Database connection manager."""
    
    client: Optional[AsyncIOMotorClient] = None
    redis_client: Optional[aioredis.Redis] = None


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


async def connect_to_redis():
    """Create Redis connection."""
    db.redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    print(f"Connected to Redis: {settings.redis_url}")


async def close_redis_connection():
    """Close Redis connection."""
    if db.redis_client:
        await db.redis_client.close()
        print("Disconnected from Redis")


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
    
    print("MongoDB initialized: All collections created with indexes")


def get_database():
    """Get database instance."""
    return db.client[settings.mongodb_url.split("/")[-1]]


def get_redis():
    """Get Redis instance."""
    return db.redis_client


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

