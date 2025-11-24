"""REST API routes (optional, for non-WebSocket endpoints)."""

from fastapi import APIRouter
from models.schemas import WebSocketMessage
from agents.supervisor import run_supervisor
from utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.post("/chat")
async def chat_endpoint(message: WebSocketMessage):
    """REST endpoint for chat (alternative to WebSocket)."""
    try:
        result = await run_supervisor(
            prompt=message.prompt,
            context=message.context,
            session_id=message.session_id
        )
        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return {"error": str(e)}

