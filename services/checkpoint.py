"""Checkpoint system for maintaining conversation context across requests."""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from models.database import get_redis
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CheckpointManager:
    """Manages conversation checkpoints using Redis."""
    
    def __init__(self):
        self.redis_prefix = "checkpoint:"
        self.default_ttl = settings.session_timeout
    
    async def save_checkpoint(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Save a checkpoint for a session.
        
        Args:
            session_id: Unique session identifier
            messages: List of conversation messages
            context: Optional context dictionary
            
        Returns:
            True if saved successfully
        """
        try:
            redis_client = get_redis()
            if not redis_client:
                logger.warning("Redis not available, using in-memory storage")
                return False
            
            checkpoint = {
                "session_id": session_id,
                "messages": messages,
                "context": context or {},
                "last_updated": datetime.now().isoformat()
            }
            
            key = f"{self.redis_prefix}{session_id}"
            await redis_client.setex(
                key,
                self.default_ttl,
                json.dumps(checkpoint)
            )
            
            logger.info(f"Saved checkpoint for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}", exc_info=True)
            return False
    
    async def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a checkpoint for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Checkpoint dictionary or None if not found
        """
        try:
            redis_client = get_redis()
            if not redis_client:
                logger.warning("Redis not available")
                return None
            
            key = f"{self.redis_prefix}{session_id}"
            data = await redis_client.get(key)
            
            if data:
                checkpoint = json.loads(data)
                logger.info(f"Loaded checkpoint for session {session_id}")
                return checkpoint
            else:
                logger.info(f"No checkpoint found for session {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}", exc_info=True)
            return None
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> bool:
        """Add a message to the checkpoint.
        
        Args:
            session_id: Unique session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Returns:
            True if added successfully
        """
        try:
            checkpoint = await self.load_checkpoint(session_id)
            
            if not checkpoint:
                checkpoint = {
                    "session_id": session_id,
                    "messages": [],
                    "context": {}
                }
            
            checkpoint["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            
            # Keep only last 50 messages to prevent checkpoint from growing too large
            if len(checkpoint["messages"]) > 50:
                checkpoint["messages"] = checkpoint["messages"][-50:]
            
            return await self.save_checkpoint(
                session_id,
                checkpoint["messages"],
                checkpoint.get("context", {})
            )
            
        except Exception as e:
            logger.error(f"Error adding message to checkpoint: {e}", exc_info=True)
            return False
    
    async def update_context(
        self,
        session_id: str,
        context_updates: Dict[str, Any]
    ) -> bool:
        """Update context in checkpoint.
        
        Args:
            session_id: Unique session identifier
            context_updates: Dictionary of context updates
            
        Returns:
            True if updated successfully
        """
        try:
            checkpoint = await self.load_checkpoint(session_id)
            
            if not checkpoint:
                checkpoint = {
                    "session_id": session_id,
                    "messages": [],
                    "context": {}
                }
            
            # Merge context updates
            checkpoint["context"].update(context_updates)
            
            return await self.save_checkpoint(
                session_id,
                checkpoint.get("messages", []),
                checkpoint["context"]
            )
            
        except Exception as e:
            logger.error(f"Error updating context: {e}", exc_info=True)
            return False
    
    async def clear_checkpoint(self, session_id: str) -> bool:
        """Clear a checkpoint for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if cleared successfully
        """
        try:
            redis_client = get_redis()
            if not redis_client:
                return False
            
            key = f"{self.redis_prefix}{session_id}"
            await redis_client.delete(key)
            
            logger.info(f"Cleared checkpoint for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing checkpoint: {e}", exc_info=True)
            return False
    
    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation messages from checkpoint.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of messages
        """
        checkpoint = await self.load_checkpoint(session_id)
        if checkpoint:
            return checkpoint.get("messages", [])
        return []
    
    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get context from checkpoint.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Context dictionary
        """
        checkpoint = await self.load_checkpoint(session_id)
        if checkpoint:
            return checkpoint.get("context", {})
        return {}


# Global checkpoint manager instance
checkpoint_manager = CheckpointManager()

