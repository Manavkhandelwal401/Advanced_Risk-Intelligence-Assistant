"""
orchestrator.py  –  AI Recommendation Module orchestrator
Thin wrapper that routes AI calls to the correct inference engine.
"""

from llm.reasoning_engine import generate_financial_insight


def generate_ai(summary: dict) -> dict:
    """
    Entry point for AI insight generation.
    Calls cloud reasoning engine (Groq via LangChain).
    """
    return generate_financial_insight(summary, "amd_cloud")
