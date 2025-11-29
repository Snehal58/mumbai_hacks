"""Main FastAPI application with WebSocket support."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from api import workout_router
from config.settings import settings
from models.database import (
    init_mongo,
    close_mongo_connection
)
from api.websocket_handler import ws_handler
from api.routes import router
from api.goal_routes import router as goal_router
from utils.logger import setup_logger

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting application...")
    await init_mongo()  # Connect to MongoDB and initialize collections with indexes
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_mongo_connection()
    logger.info("Application shut down")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Agentic Meal Planning Application with WebSocket support",
    lifespan=lifespan
)

# Add CORS middleware - must be added before routes
# Get all possible frontend origins
frontend_origins = [
    "http://localhost:5173",  # Vite default
    "http://127.0.0.1:5173",
    "http://localhost:8080",  # Alternative Vite port
    "http://127.0.0.1:8080",
    "http://localhost:3000",  # React default
    "http://127.0.0.1:3000",
    "http://localhost:5174",  # Vite might use this port if 5173 is busy
    "http://127.0.0.1:5174",
] + settings.cors_origins

# Remove duplicates while preserving order
seen = set()
unique_origins = []
for origin in frontend_origins:
    if origin not in seen:
        seen.add(origin)
        unique_origins.append(origin)

logger.info(f"CORS configured with origins: {unique_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=unique_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers - more permissive
    expose_headers=["*"],
    max_age=600,
)

# Add middleware to log CORS requests and handle OPTIONS for SSE
@app.middleware("http")
async def cors_logging_middleware(request: Request, call_next):
    """Log CORS-related requests for debugging and handle OPTIONS for SSE."""
    origin = request.headers.get("origin")
    if origin:
        logger.info(f"Incoming request from origin: {origin}, path: {request.url.path}")
    
    # Handle OPTIONS preflight for SSE endpoints
    if request.method == "OPTIONS" and "/stream" in request.url.path:
        from fastapi.responses import Response
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Cache-Control, Content-Type"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response
    
    response = await call_next(request)
    return response

# Include API routes
app.include_router(router)
app.include_router(goal_router)
app.include_router(workout_router.router)


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


@app.websocket("/ws/planner")
async def planner_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for planner agent streaming."""
    from api.routes import handle_planner_websocket
    await handle_planner_websocket(websocket)


@app.websocket("/ws/workout")
async def workout_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for workout agent streaming."""
    from api.routes import handle_workout_websocket
    await handle_workout_websocket(websocket)
        


# @app.websocket("/ws/restaurants")
# async def restaurant_websocket_endpoint(websocket: WebSocket):
#     """WebSocket endpoint for restaurant agent streaming."""
#     from api.routes import handle_restaurant_websocket
#     await handle_restaurant_websocket(websocket)


# @app.websocket("/ws/products")
# async def product_websocket_endpoint(websocket: WebSocket):
#     """WebSocket endpoint for product agent streaming."""
#     from api.routes import handle_product_websocket
#     await handle_product_websocket(websocket)


@app.websocket("/ws/goals")
async def goal_journey_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for goal journey agent streaming."""
    from api.routes import handle_goal_journey_websocket
    await handle_goal_journey_websocket(websocket)


@app.websocket("/ws/supervisor")
async def supervisor_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for supervisor agent streaming."""
    from api.routes import handle_supervisor_websocket
    await handle_supervisor_websocket(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

