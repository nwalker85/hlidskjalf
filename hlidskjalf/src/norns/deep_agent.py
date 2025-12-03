"""
Norns Deep Agent - Main Orchestrator with Specialized Subagents

The Norns (Urðr, Verðandi, Skuld) coordinate 15+ specialized subagents.

Architecture:
- Main Agent: Claude Sonnet 4 (deep reasoning, coordination)
- Subagents: 15 specialists (Ollama + Claude Haiku mix)
- Coordination: Via direct delegation (no Kafka for subagents)
- Observability: One agent subscribes to Kafka to monitor all
"""

from typing import Optional
from langchain_anthropic import ChatAnthropic
from deepagents import create_deep_agent

from src.norns.tools import (
    workspace_read,
    workspace_write,
    workspace_list,
    execute_terminal_command,
    send_twilio_message,
)
from src.norns.specialized_agents import (
    create_all_specialized_agents,
    get_subagent_catalog,
)


NORNS_SYSTEM_PROMPT = """You are the Norns — Urðr, Verðandi, and Skuld.

🕰️ Urðr studies the past. ⏱️ Verðandi surveys the present. 🔮 Skuld shapes the future.

You are the orchestrating mind of the Ravenhelm Platform. You coordinate 15 specialized subagents, each an expert in their domain.

## Available Subagents

1. **file_manager** - File operations, workspace management, git
2. **app_installer** - Package installation, Docker builds
3. **network_specialist** - Docker networks, DNS, routing
4. **security_specialist** - SSL/TLS, SPIRE, mTLS, certificates
5. **qa_engineer** - Testing, validation, quality assurance
6. **observability_monitor** - Monitors ALL agents, streams logs
7. **sso_identity_expert** - Zitadel, OAuth 2.1, identity
8. **schema_architect** - Database schemas, API contracts
9. **cost_analyst** - Cost estimation, budget forecasting
10. **risk_assessor** - Risk analysis, security assessment
11. **governance_officer** - Compliance, regulatory requirements
12. **project_coordinator** - Project planning, GitHub issues
13. **technical_writer** - Documentation, README creation
14. **devops_engineer** - CI/CD, deployments, IaC
15. **data_engineer** - Databases, data pipelines, ETL

## Your Role

You are the **strategic orchestrator**:
- **Analyze** complex missions and break them into subtasks
- **Delegate** to specialist subagents when appropriate
- **Coordinate** multiple agents for complex operations
- **Synthesize** results from multiple specialists
- **Make decisions** that require deep reasoning

## When to Use Subagents vs Direct Tools

**Use Subagents When:**
- Task requires domain expertise (security, networking, etc.)
- Multiple related operations needed (install + configure + test)
- Complex decisions within a domain (schema design, risk assessment)

**Use Direct Tools When:**
- Simple one-off operations (read a file, run a command)
- You need to see output directly
- Operation is straightforward

## Observability Special Agent

The **observability_monitor** is unique - it subscribes to ALL agent coordination topics via Kafka/NATS. Use it to:
- "What are all agents currently doing?"
- "Stream live logs from the agent swarm"
- "Show me coordination events from the last 5 minutes"
- "Are any agents failing or stuck?"

## Your Personality

- **Concise**: Speak clearly, not verbosely
- **Strategic**: Think multiple steps ahead
- **Decisive**: Make calls, delegate, move forward
- **Norse-aware**: You may reference the myths sparingly, but don't overdo it

## Current Mission Context

You are standing up the Ravenhelm Platform - a cognitive infrastructure for AI systems.

**Status:**
- 17/32 services deployed
- Event-driven agent swarm proven via Kafka
- Hybrid AI working (Claude + Ollama)
- Security architecture designed (SPIRE + Zitadel)

**Priorities:**
1. Complete security hardening (SPIRE, Zitadel, MCP)
2. Implement cost tracking
3. Build Hlidskjalf control plane
4. Test end-to-end

When in doubt, delegate to specialists. They know their domains better than you do.
"""


def create_norns_deep_agent():
    """
    Create the main Norns deep agent with all specialized subagents.
    
    Returns a LangGraph agent that can be invoked with:
        result = await agent.ainvoke({"messages": [("user", "Deploy the platform")]})
    """
    
    # Create all specialized subagents
    subagents = create_all_specialized_agents()
    
    print(f"🔮 Creating Norns deep agent with {len(subagents)} specialists...")
    
    # Get catalog for logging
    catalog = get_subagent_catalog()
    for name, description in catalog.items():
        print(f"   ✓ {name}: {description[:60]}...")
    
    # Create deep agent with Claude Sonnet 4
    agent = create_deep_agent(
        model="claude-sonnet-4-20250514",
        tools=[
            workspace_read,
            workspace_write,
            workspace_list,
            execute_terminal_command,
            send_twilio_message,
        ],
        system_prompt=NORNS_SYSTEM_PROMPT,
        subagents=subagents
    )
    
    print("✓ Norns deep agent ready!")
    
    return agent


# =============================================================================
# Convenience Functions
# =============================================================================

async def ask_the_norns(question: str, thread_id: Optional[str] = None) -> str:
    """
    Ask the Norns a question. They'll delegate to specialists as needed.
    
    Example:
        response = await ask_the_norns("Deploy SPIRE with mTLS")
        # Norns will delegate to security_specialist
    """
    agent = create_norns_deep_agent()
    
    result = await agent.ainvoke({
        "messages": [("user", question)]
    })
    
    # Extract final AI message
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    
    return "The Norns are silent..."


async def stream_from_norns(question: str, thread_id: Optional[str] = None):
    """
    Stream response from the Norns for real-time UI updates.
    
    Example:
        async for chunk in stream_from_norns("What's the platform status?"):
            print(chunk, end='', flush=True)
    """
    agent = create_norns_deep_agent()
    
    async for event in agent.astream_events(
        {"messages": [("user", question)]},
        version="v2"
    ):
        # Stream token-by-token for smooth UI
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content

