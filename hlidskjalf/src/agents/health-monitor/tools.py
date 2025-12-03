"""
Tools for Health Monitor agent.
"""

from langchain_core.tools import tool


# =============================================================================
# Health Monitor Tools
# =============================================================================

@tool
def agent_status() -> str:
    """Report the current status of this agent."""
    return "Health Monitor agent is operational and ready for tasks."


# Add custom tools here


# =============================================================================
# Tool Collection
# =============================================================================

HEALTH_MONITOR_TOOLS = [
    agent_status,
]
