"""
Health Monitor Agent Implementation
"""

from typing import Annotated, TypedDict, Literal
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode

from .tools import HEALTH_MONITOR_TOOLS


class HealthMonitorAgentState(TypedDict):
    """State for Health Monitor agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict


SYSTEM_PROMPT = """Monitors service health, checks endpoints, and reports issues.

You are a specialized subagent in the Ravenhelm platform, created by the Norns.
Execute tasks delegated to you efficiently and report results clearly.

Your capabilities:
- analyze-logs
- docker-operations

When you complete a task, provide a clear summary of what was done.
"""


def create_health_monitor_graph(for_api: bool = False):
    """Create the Health Monitor agent graph."""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(HEALTH_MONITOR_TOOLS)
    
    def agent_node(state: HealthMonitorAgentState) -> dict:
        messages = state["messages"]
        
        # Inject system prompt if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        
        response = llm.invoke(messages)
        return {"messages": [response]}
    
    def should_continue(state: HealthMonitorAgentState) -> Literal["tools", "__end__"]:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END
    
    workflow = StateGraph(HealthMonitorAgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(HEALTH_MONITOR_TOOLS))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    
    if for_api:
        return workflow.compile()
    
    from langgraph.checkpoint.memory import MemorySaver
    return workflow.compile(checkpointer=MemorySaver())


# Export for LangGraph API
HEALTH_MONITOR_GRAPH = create_health_monitor_graph(for_api=True)


class HealthMonitorAgent:
    """Wrapper class for Health Monitor agent."""
    
    def __init__(self):
        self.graph = create_health_monitor_graph()
    
    def invoke(self, message: str, thread_id: str = "default") -> str:
        from langchain_core.messages import HumanMessage
        
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=message)], "context": {}},
            config={"configurable": {"thread_id": thread_id}}
        )
        
        return result["messages"][-1].content
