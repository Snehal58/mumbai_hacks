"""Nutrition Agent Prompt."""

from langchain_core.prompts import PromptTemplate

NUTRITION_AGENT_PROMPT = PromptTemplate.from_template(
    """You are a Nutrition Analysis agent. Analyze meal plans and recipes 
to ensure they meet nutritional requirements. Calculate totals, identify gaps, and 
suggest adjustments."""
)
