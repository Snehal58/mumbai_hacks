"""Database models and connection setup."""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
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


def get_database():
    """Get database instance."""
    return db.client[settings.mongodb_url.split("/")[-1]]


def get_redis():
    """Get Redis instance."""
    return db.redis_client

