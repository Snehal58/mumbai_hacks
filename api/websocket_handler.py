"""WebSocket message handler for agent communication."""

import json
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket
from models.schemas import WebSocketMessage, WebSocketResponse
from agents.supervisor import run_supervisor
from utils.logger import setup_logger
from utils.helpers import format_agent_response

logger = setup_logger(__name__)


class WebSocketHandler:
    """Handler for WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: WebSocketResponse):
        """Send a message to a specific session."""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message.dict())
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                self.disconnect(session_id)
    
    async def handle_message(self, websocket: WebSocket, message: str, session_id: str):
        """Handle incoming WebSocket message."""
        try:
            # Parse message
            data = json.loads(message)
            ws_message = WebSocketMessage(**data)
            
            # Use provided session_id or generate one
            current_session_id = ws_message.session_id or session_id
            
            # Send thinking message
            await self.send_message(
                current_session_id,
                WebSocketResponse(
                    type="thinking",
                    content="Analyzing your request...",
                    session_id=current_session_id
                )
            )
            
            # Run supervisor with callback for intermediate updates
            async def progress_callback(step: str, content: str):
                """Callback for progress updates."""
                response_type = "thinking"
                if "finding" in step.lower() or "recipe" in step.lower():
                    response_type = "finding_records"
                elif "searching" in step.lower() or "restaurant" in step.lower():
                    response_type = "searching_more"
                
                await self.send_message(
                    current_session_id,
                    WebSocketResponse(
                        type=response_type,
                        content=content,
                        session_id=current_session_id
                    )
                )
            
            # Run the supervisor
            result = await run_supervisor(
                prompt=ws_message.prompt,
                context=ws_message.context,
                session_id=current_session_id
            )
            
            # Send final output
            await self.send_message(
                current_session_id,
                WebSocketResponse(
                    type=result.get("type", "output"),
                    content=result.get("content", result),
                    session_id=current_session_id
                )
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WebSocket message: {e}")
            await self.send_message(
                session_id,
                WebSocketResponse(
                    type="error",
                    content="Invalid message format",
                    session_id=session_id
                )
            )
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_message(
                session_id,
                WebSocketResponse(
                    type="error",
                    content=f"Error processing request: {str(e)}",
                    session_id=session_id
                )
            )


# Global WebSocket handler instance
ws_handler = WebSocketHandler()

