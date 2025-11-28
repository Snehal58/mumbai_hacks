"""WebSocket message schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class WebSocketMessage(BaseModel):
    """WebSocket message from client."""
    prompt: str = Field(..., description="User's natural language prompt")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context (location, budget, preferences, etc.)"
    )


class WebSocketResponse(BaseModel):
    """WebSocket response to client."""
    type: str = Field(..., description="Response type: thinking, finding_records, searching_more, output")
    content: Any = Field(..., description="Response content")
    session_id: Optional[str] = Field(None, description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.now)

