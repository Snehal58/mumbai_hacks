"""Checkpoint system for maintaining conversation context across requests."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from models.database import get_checkpoints_collection
from config.settings import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CheckpointManager:
    """Manages conversation checkpoints using MongoDB."""
    
    def __init__(self):
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
            checkpoints_collection = get_checkpoints_collection()
            if not checkpoints_collection:
                logger.warning("MongoDB not available")
                return False
            
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.default_ttl)
            
            checkpoint = {
                "session_id": session_id,
                "messages": messages,
                "context": context or {},
                "last_updated": now,
                "expires_at": expires_at
            }
            
            # Use upsert to update or insert
            await checkpoints_collection.update_one(
                {"session_id": session_id},
                {"$set": checkpoint},
                upsert=True
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
            checkpoints_collection = get_checkpoints_collection()
            if not checkpoints_collection:
                logger.warning("MongoDB not available")
                return None
            
            # Clean up expired checkpoints first
            await self._cleanup_expired_checkpoints()
            
            checkpoint_doc = await checkpoints_collection.find_one({
                "session_id": session_id,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if checkpoint_doc:
                # Convert ObjectId to string and datetime to ISO format for JSON serialization
                checkpoint = {
                    "session_id": checkpoint_doc["session_id"],
                    "messages": checkpoint_doc["messages"],
                    "context": checkpoint_doc.get("context", {}),
                    "last_updated": checkpoint_doc["last_updated"].isoformat() if isinstance(checkpoint_doc["last_updated"], datetime) else checkpoint_doc["last_updated"]
                }
                logger.info(f"Loaded checkpoint for session {session_id}")
                return checkpoint
            else:
                logger.info(f"No checkpoint found for session {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}", exc_info=True)
            return None
    
    async def _cleanup_expired_checkpoints(self):
        """Clean up expired checkpoints."""
        try:
            checkpoints_collection = get_checkpoints_collection()
            if not checkpoints_collection:
                return
            
            result = await checkpoints_collection.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} expired checkpoints")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired checkpoints: {e}", exc_info=True)
    
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
            checkpoints_collection = get_checkpoints_collection()
            if not checkpoints_collection:
                return False
            
            result = await checkpoints_collection.delete_one({"session_id": session_id})
            
            if result.deleted_count > 0:
                logger.info(f"Cleared checkpoint for session {session_id}")
                return True
            else:
                logger.info(f"No checkpoint found to clear for session {session_id}")
                return False
            
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

