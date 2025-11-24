"""Helper utility functions."""

import json
from typing import Any, Dict


def format_agent_response(response_type: str, content: Any, session_id: str = None) -> Dict[str, Any]:
    """Format agent response for WebSocket."""
    return {
        "type": response_type,
        "content": content,
        "session_id": session_id,
    }


def parse_nutrition_goal(text: str) -> Dict[str, float]:
    """Extract nutrition goals from text using simple parsing."""
    # This is a placeholder - actual implementation would use NLP
    nutrition = {}
    text_lower = text.lower()
    
    # Simple keyword extraction (can be enhanced with NLP)
    if "calorie" in text_lower or "kcal" in text_lower:
        # Extract number before calorie/kcal
        import re
        matches = re.findall(r'(\d+)\s*(?:calorie|kcal)', text_lower)
        if matches:
            nutrition["calories"] = float(matches[0])
    
    if "protein" in text_lower:
        import re
        matches = re.findall(r'(\d+)\s*g\s*protein', text_lower)
        if matches:
            nutrition["protein"] = float(matches[0])
    
    return nutrition

