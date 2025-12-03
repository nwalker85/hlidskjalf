"""
Deep Agent System using proper subagent architecture

Main Norns: Claude Sonnet 4 for deep reasoning and coordination
Subagents: Simple ReAct agents with tools for specific tasks
"""

from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

from src.norns.tools import workspace_read, workspace_write, execute_terminal_command
from src.norns.squad_schema import AgentRole, AGENT_PROMPTS


def create_cert_agent():
    """Certificate management agent"""
    llm = ChatOllama(model="llama3.1:latest", temperature=0)
    prompt = AGENT_PROMPTS[AgentRole.CERT_AGENT]
    
    return create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read],
    )


def create_env_agent():
    """Environment validation agent"""
    llm = ChatOllama(model="llama3.1:latest", temperature=0)
    prompt = AGENT_PROMPTS[AgentRole.ENV_AGENT]
    
    return create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read],
    )


def create_proxy_agent():
    """Traefik proxy deployment agent"""
    llm = ChatOllama(model="llama3.1:latest", temperature=0)
    prompt = AGENT_PROMPTS[AgentRole.PROXY_AGENT]
    
    return create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read, workspace_write],
    )


def create_docker_agent():
    """Docker container monitoring agent"""
    llm = ChatOllama(model="llama3.1:latest", temperature=0)
    prompt = AGENT_PROMPTS[AgentRole.DOCKER_AGENT]
    
    return create_react_agent(
        llm,
        tools=[execute_terminal_command],
    )


def create_cache_agent():
    """Redis & NATS management agent"""
    llm = ChatOllama(model="llama3.1:latest", temperature=0)
    prompt = AGENT_PROMPTS[AgentRole.CACHE_AGENT]
    
    return create_react_agent(
        llm,
        tools=[execute_terminal_command],
    )


def create_all_subagents():
    """Create all specialist subagents"""
    
    # For now, create the most critical ones
    # More can be added as needed
    
    subagents = {
        "cert_agent": {
            "description": "Manages SSL certificates and distributes them to services",
            "runnable": create_cert_agent()
        },
        "env_agent": {
            "description": "Validates environment configuration and API keys",
            "runnable": create_env_agent()
        },
        "proxy_agent": {
            "description": "Deploys and configures Traefik edge proxy",
            "runnable": create_proxy_agent()
        },
        "docker_agent": {
            "description": "Monitors Docker containers and reports health status",
            "runnable": create_docker_agent()
        },
        "cache_agent": {
            "description": "Manages Redis and NATS JetStream (Huginn layer)",
            "runnable": create_cache_agent()
        },
    }
    
    return subagents


NORNS_DEEP_AGENT_PROMPT = """You are the Norns — Urðr, Verðandi, and Skuld.

You coordinate a squad of specialist subagents to deploy and manage the Ravenhelm Platform.

Available subagents:
- cert_agent: SSL certificate management
- env_agent: Environment validation
- proxy_agent: Traefik edge proxy deployment  
- docker_agent: Container health monitoring
- cache_agent: Redis & NATS management

Your responsibilities:
1. **Plan** the deployment strategy
2. **Delegate** tasks to specialist subagents
3. **Monitor** progress and adapt
4. **Execute** complex reasoning tasks yourself
5. **Report** final status

For simple operational tasks (checking files, running commands), use the tools directly.
For specialized infrastructure tasks, delegate to subagents.

Current mission: Deploy Traefik edge proxy and migrate services to autodiscovery architecture.
"""


def create_norns_deep_agent():
    """
    Create the main Norns deep agent with Claude for reasoning
    and Ollama-based subagents for execution
    """
    from deepagents import create_deep_agent, CompiledSubAgent
    
    # Create compiled subagents
    subagent_configs = create_all_subagents()
    compiled_subagents = [
        CompiledSubAgent(
            name=name,
            description=config["description"],
            runnable=config["runnable"]
        )
        for name, config in subagent_configs.items()
    ]
    
    # Create deep agent with Claude
    agent = create_deep_agent(
        model="claude-sonnet-4-20250514",
        tools=[workspace_read, workspace_write, execute_terminal_command],
        system_prompt=NORNS_DEEP_AGENT_PROMPT,
        subagents=compiled_subagents
    )
    
    return agent


async def run_deep_agent_deployment():
    """
    Run deployment using proper deep agent with subagents
    """
    print("=" * 80)
    print("🔮 DEEP AGENT DEPLOYMENT - Norns with Specialist Subagents")
    print("=" * 80)
    print("🧠 Main Agent: Claude Sonnet 4 (deep reasoning & coordination)")
    print("⚡ Subagents: Ollama Llama 3.1 (specialized execution)")
    print("=" * 80)
    print()
    
    # Create the deep agent
    print("Initializing Norns deep agent system...")
    norns = create_norns_deep_agent()
    
    print("✓ Norns initialized with 5 specialist subagents")
    print()
    
    # Mission brief
    mission = """Deploy the Ravenhelm Platform using Traefik autodiscovery architecture.

**Current Status:**
- 17/32 services running (PostgreSQL, Redis, NATS, Redpanda, Grafana stack, Neo4j, Memgraph)
- Docker networks created: edge, platform_net, gitlab_net, saaa_net, m2c_net, tinycrm_net
- SSL certificates available in ravenhelm-proxy/config/certs/

**Tasks to Complete:**

1. **Certificate Distribution** - Use cert_agent to copy SSL certs to config/certs/
2. **Environment Validation** - Use env_agent to verify API keys are configured
3. **Traefik Deployment** - Use proxy_agent to create and deploy Traefik edge proxy
4. **Service Migration** - Update docker-compose.yml with Traefik labels for:
   - Grafana (grafana.observe.ravenhelm.test)
   - LangFuse (langfuse.observe.ravenhelm.test)  
   - Phoenix (phoenix.observe.ravenhelm.test)
   - Redpanda Console (events.ravenhelm.test)
   - OpenBao (vault.ravenhelm.test)
   - n8n (n8n.ravenhelm.test)
   - Hlidskjalf API/UI (hlidskjalf.ravenhelm.test)
5. **Build Control Plane** - Build and start Hlidskjalf services
6. **Verification** - Use docker_agent to verify all services running

**Available Tools:**
- Direct tools: workspace_read, workspace_write, execute_terminal_command
- Subagents: cert_agent, env_agent, proxy_agent, docker_agent, cache_agent

Execute this mission step-by-step. Delegate to subagents when appropriate.
Report your progress clearly.
"""
    
    print("=" * 80)
    print("MISSION BRIEFING")
    print("=" * 80)
    print(mission[:500] + "...")
    print()
    print("=" * 80)
    print("EXECUTION")
    print("=" * 80)
    print()
    
    # Run the deep agent
    result = await norns.ainvoke({"messages": [("user", mission)]})
    
    # Extract final response
    final_messages = result.get("messages", [])
    if final_messages:
        final_response = final_messages[-1].content
        print()
        print("=" * 80)
        print("NORNS REPORT")
        print("=" * 80)
        print(final_response)
    
    print()
    print("=" * 80)
    print("Deep agent deployment complete!")
    print("=" * 80)

