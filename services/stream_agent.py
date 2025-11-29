"""Generic streaming service for agent chat interactions."""

import asyncio
import json
import uuid
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage
from services.checkpoint import checkpoint_manager
from utils.logger import setup_logger
from langchain_core.messages import SystemMessage
import re

logger = setup_logger(__name__)


class StreamAgentService:
    """Generic service for streaming agent interactions with checkpoint management."""
    
    def __init__(self):
        """Initialize the stream agent service."""
        pass
    
    async def stream_agent(
        self,
        agent: Any,
        prompt: str,
        session_id: str,
        user_id: Optional[str] = None,
        max_history: int = 20
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream agent execution with checkpoint management.
        
        Args:
            agent: LangGraph agent instance
            prompt: User's prompt/message
            session_id: Session identifier for context continuity
            user_id: Optional user identifier
            max_history: Maximum number of messages to keep in history
            
        Yields:
            Dictionary events with 'event' and 'data' keys:
            - 'thinking': Agent is processing
            - 'question': Agent is asking a question
            - 'tool_call': Agent is calling a tool
            - 'done': Agent completed with final response
            - 'error': An error occurred
        """
        try:
            # Load checkpoint for context
            checkpoint = await checkpoint_manager.load_checkpoint(session_id)
            messages_history = checkpoint.get("messages", []) if checkpoint else []
            context = checkpoint.get("context", {}) if checkpoint else {}
            
            # Add user message to history
            await checkpoint_manager.add_message(session_id, "user", prompt)
            
            # Build conversation history for the agent
            conversation_messages = []
            if messages_history:
                # Convert checkpoint messages to LangChain message format
                for msg in messages_history[-max_history:]:  # Last N messages for context
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        conversation_messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        conversation_messages.append(AIMessage(content=content))
            
            # Add current user message
            conversation_messages.append(HumanMessage(content=prompt))
            
            # Add system message with user_id and current time for all agents if user_id is available
            if user_id:
                current_time = datetime.utcnow().isoformat()
                system_content = f"User ID: {user_id}\nCurrent Time: {current_time}"
                
                # Check if there's already a system message
                if not conversation_messages or not isinstance(conversation_messages[0], SystemMessage):
                    # Insert new system message at the beginning
                    conversation_messages.insert(0, SystemMessage(content=system_content))
                elif isinstance(conversation_messages[0], SystemMessage):
                    # Update existing system message to include user_id and current time
                    existing_content = conversation_messages[0].content
                    # Only add if not already present to avoid duplicates
                    if f"User ID: {user_id}" not in existing_content:
                        conversation_messages[0] = SystemMessage(content=f"{existing_content}\n\n{system_content}")
                    else:
                        # Update the current time if user_id already exists
                        updated_content = re.sub(
                            r'Current Time: [^\n]+',
                            f'Current Time: {current_time}',
                            existing_content
                        )
                        conversation_messages[0] = SystemMessage(content=updated_content)
            
            # Create initial state with conversation history
            initial_state = {
                "messages": conversation_messages if len(conversation_messages) > 1 else [HumanMessage(content=prompt)]
            }
            
            logger.info(f"Starting agent stream for session {session_id}, user_id: {user_id}")
            
            # Yield initial thinking event
            yield {
                "event": "thinking",
                "data": {"message": "Analyzing your request..."},
                "id": None
            }
            
            # Stream agent execution
            try:
                final_state = None
                
                # Stream the agent
                try:
                    async for event in agent.astream(initial_state):
                        if isinstance(event, dict):
                            # Store final state if we see __end__
                            if "__end__" in event:
                                final_state = event["__end__"]
                                break
                            
                            # Check for messages in the event
                            for node_name, node_data in event.items():
                                if node_name != "__end__" and isinstance(node_data, dict) and "messages" in node_data:
                                    messages_list = node_data["messages"]
                                    if messages_list:
                                        last_message = messages_list[-1]
                                        
                                        # Check if it's a tool call
                                        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                                            for tool_call in last_message.tool_calls:
                                                tool_name = tool_call.get("name", "unknown") if isinstance(tool_call, dict) else getattr(tool_call, "name", "unknown")
                                                yield {
                                                    "event": "tool_call",
                                                    "data": {
                                                        "tool": tool_name,
                                                        "input": tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                                                    },
                                                    "id": None
                                                }
                        
                        await asyncio.sleep(0.05)
                    
                    # If we didn't get final state from stream, invoke to get final result
                    if final_state is None:
                        logger.info("Getting final state from agent invocation")
                        try:
                            final_state = await asyncio.wait_for(
                                agent.ainvoke(initial_state),
                                timeout=60.0
                            )
                        except asyncio.TimeoutError:
                            logger.error("Agent invocation timed out")
                            yield {
                                "event": "error",
                                "data": {"message": "Agent execution timed out. Please try again."},
                                "id": None
                            }
                            return
                    
                except asyncio.TimeoutError:
                    logger.error("Agent stream timed out")
                    yield {
                        "event": "error",
                        "data": {"message": "Request timed out. Please try again."},
                        "id": None
                    }
                    return
                
                # Process final response
                messages = final_state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                    
                    # Save assistant response to checkpoint
                    await checkpoint_manager.add_message(session_id, "assistant", str(content))
                    
                    # Check if the response is a question or final answer
                    content_str = str(content).strip()
                    
                    # Determine if this is a question or final answer
                    # Simple heuristic: if it ends with '?' it's likely a question
                    # Otherwise, check if it contains JSON (final goal data)
                    is_question = content_str.endswith('?') or (
                        '?' in content_str and 
                        not (content_str.strip().startswith('{') or content_str.strip().startswith('['))
                    )
                    
                    # Try to parse as JSON (final goal data)
                    parsed_content = None
                    try:
                        import re
                        json_match = re.search(r'(\{[\s\S]*\})', content_str)
                        if json_match:
                            parsed_content = json.loads(json_match.group(1))
                            is_question = False
                    except (json.JSONDecodeError, Exception):
                        pass
                    
                    if is_question:
                        # This is a question - yield question event
                        yield {
                            "event": "question",
                            "data": {
                                "question": content_str,
                            },
                            "id": None
                        }
                        return
                    else:
                        # This is a final answer - yield done event
                        response_content = parsed_content if parsed_content else content_str
                        
                        yield {
                            "event": "done",
                            "data": {
                                "content": response_content,
                                "complete": True,
                                "session_id": session_id
                            },
                            "id": None
                        }
                else:
                    yield {
                        "event": "error",
                        "data": {"message": "No response generated from agent"},
                        "id": None
                    }
                    
            except Exception as e:
                logger.error(f"Error in agent stream: {e}", exc_info=True)
                yield {
                    "event": "error",
                    "data": {"message": f"Error processing request: {str(e)}"},
                    "id": None
                }
                
        except Exception as e:
            logger.error(f"Error in stream_agent: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": {"message": f"Error processing request: {str(e)}"},
                "id": None
            }


# Global instance
stream_agent_service = StreamAgentService()

