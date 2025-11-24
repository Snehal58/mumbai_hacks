"""Main FastAPI application with WebSocket support."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from config.settings import settings
from models.database import (
    connect_to_mongo,
    close_mongo_connection,
    connect_to_redis,
    close_redis_connection
)
from api.websocket_handler import ws_handler
from utils.logger import setup_logger

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting application...")
    await connect_to_mongo()
    await connect_to_redis()
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_mongo_connection()
    await close_redis_connection()
    logger.info("Application shut down")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Agentic Meal Planning Application with WebSocket support",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Meal Planner API",
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent communication."""
    session_id = str(uuid.uuid4())
    
    try:
        await ws_handler.connect(websocket, session_id)
        
        while True:
            # Receive message from client
            message = await websocket.receive_text()
            logger.info(f"Received message from {session_id}: {message[:100]}...")
            
            # Handle message
            await ws_handler.handle_message(websocket, message, session_id)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        ws_handler.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_handler.disconnect(session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

