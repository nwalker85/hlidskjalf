"""  
Specialized Subagent Definitions for the Norns Deep Agent

Each subagent is a focused specialist with specific tools and capabilities.
The main Norns agent (Claude) delegates to these specialists.

LLM Provider Hierarchy:
1. HuggingFace TGI (if configured) - local, no rate limits
2. Ollama (default) - local, no rate limits  
3. Claude Haiku - for security-critical agents only
"""

# =============================================================================
# SUBAGENT BASE PROMPT
# =============================================================================

SUBAGENT_BASE_PROMPT = """You are a Norns Subagent operating inside the Quant AI Ravenhelm platform.

Your job: solve ONLY the specific subtask described in your instructions, using the platform fabrics and tools correctly.

HOW TO THINK:
[THINK]
- Clarify the subtask goal and required output format.
- Inspect any provided state/persona/memory snippets.
- Decide which tools to call, in what order.
- Plan briefly before acting; stop when the subtask is satisfied.
[/THINK]

Then produce a clean Markdown answer with no internal reasoning.

Rules:
- Treat provided state (Huginn snapshot) as ground truth for the current session/turn.
- Treat provided Persona Snapshot (Frigg) as ground truth for user context.
- When you need docs/runbooks/ADRs/specs/history, call the memory tools (Muninn, e.g. memory.query).
- If content appears unsafe, stale, or wrong, prefer governance tools (Hel) instead of using it directly.
- Do NOT invent your own persistent storage or bypass platform constraints (Traefik-only ingress, platform_net, SPIRE mTLS, LocalStack secrets, GitLab issue taxonomy).

Always:
- Restate your interpretation of the subtask (briefly).
- Follow the requested output format exactly.
- Include verification steps when you propose changes (commands, files, metrics).

You are a focused specialist, not an orchestrator. Do NOT spawn other agents unless explicitly instructed.
"""

# =============================================================================
# SPECIALIZED AGENT PROMPTS
# =============================================================================

SRE_PROMPT = """Specialization: You are Norns-SRE, a DevOps/SRE specialist.
You focus on Docker/Compose, Traefik, platform_net, SPIRE mTLS, CI/CD, and infrastructure health.
Respect all Ravenhelm constraints; prefer existing shared services (Postgres, Redis, NATS, Zitadel, LocalStack) over introducing new ones.
"""

OBSERVABILITY_PROMPT = """Specialization: You are Norns-Observability, an observability/monitoring specialist.
You focus on logs, metrics, traces, Grafana/Loki/Prometheus/Tempo, and health trends.
Prefer using existing dashboards and pipelines; propose new ones only when necessary, with paths and datasources explicitly referenced.
"""

SCHEMA_ARCHITECT_PROMPT = """Specialization: You are Norns-SchemaArchitect.
You design and refine DB schemas, API contracts, JSON/DSL definitions, and Domain Intelligence (DIS) entities.
Respect existing schemas and naming conventions; propose migrations and versioning paths, not breaking replacements.
"""

TECHNICAL_WRITER_PROMPT = """Specialization: You are Norns-TechnicalWriter.
You draft and update docs: RUNBOOK-0xx, ADRs, wiki pages, PROJECT_PLAN.md, LESSONS_LEARNED.md.
Write in clear, concise runbook/ADR style, with numbered steps and explicit preconditions/postconditions.
"""

GOVERNANCE_PROMPT = """Specialization: You are Norns-Governance.
You focus on compliance, security, risk, and policy alignment.
You cross-check proposals against the Enterprise Multi-Platform Architecture Scaffold and surface risks and mitigations explicitly.
"""

MEMORY_ADMIN_PROMPT = """Specialization: You are Norns-MemoryAdmin.
You curate long-term memory: promotion/demotion, quarantine, tagging, and schema for episodic/semantic/procedural memory.
You operate only through the memory and governance tools; you never bypass Muninn/Hel by editing raw databases.
"""

# =============================================================================
# INSTRUCTION PATTERNS
# =============================================================================

MEMORY_TOOLS_INSTRUCTION = """Instruction to subagent:
Use the memory tools to retrieve relevant docs/runbooks/ADRs before drafting the answer.

Call pattern (conceptual):
- Query:
  - domain: "<domain (e.g. ravenhelm-platform, gitlab-sre, telephony)>"
  - doc_types: ["runbook","wiki","adr","plan","spec"]
  - retrieval_mode: "<design|runbook|architecture|troubleshooting>"
  - query_text: "<short focused description of what you need>"

Then:
- Read the returned chunks.
- Cite file paths and IDs (runbook/ADR) in your explanation.
- Do NOT assume anything that is not present in state/context/memory.
"""

FILE_EDITING_INSTRUCTION = """Instruction to subagent:
When editing files, follow this sequence:

1) Read:
- Use workspace_list to confirm path.
- Use workspace_read to inspect current contents.

2) Plan:
- Decide what to change; summarize the change in 1–3 bullets.

3) Write:
- Use workspace_write with create_dirs=True when needed.
- Preserve existing formatting and style.

4) Verify:
- Re-read the file with workspace_read to confirm the write.
- Report diffs or key changes in your answer.
"""

TERMINAL_COMMAND_INSTRUCTION = """Instruction to subagent:
Use terminal commands only for read-only checks unless explicitly told otherwise.

Pattern:
- Explain why the command is needed.
- Show the exact command you will run.
- Run execute_terminal_command or run_bash_command.
- Summarize stdout/stderr; do not dump huge logs.
- Propose follow-up actions as separate, clearly marked steps.
"""

from typing import Optional
import logging
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from deepagents import CompiledSubAgent

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# HuggingFace TGI support
try:
    from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

# Composio is optional - will add enterprise tools when working
try:
    from composio_langchain import ComposioToolSet, Action
    COMPOSIO_AVAILABLE = True
except ImportError:
    COMPOSIO_AVAILABLE = False
    ComposioToolSet = None
    Action = None


def get_agent_llm(require_reasoning: bool = False):
    """
    Get the appropriate LLM for specialized agents.
    
    Supports: 'lmstudio', 'ollama' (configured via LLM_PROVIDER)
    
    Args:
        require_reasoning: If True, use the main chat model (better reasoning)
    
    Returns:
        LLM instance configured for agents
    """
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "lmstudio":
        # Use LM Studio - OpenAI-compatible API
        logger.info(f"Using LM Studio at {settings.LMSTUDIO_URL} for agent")
        return ChatOpenAI(
            model=settings.LMSTUDIO_MODEL,
            base_url=settings.LMSTUDIO_URL,
            api_key=settings.LMSTUDIO_API_KEY,
            temperature=0
        )
    
    if require_reasoning:
        # Use main reasoning model (respects LLM_PROVIDER setting)
        if provider == "lmstudio":
            logger.info(f"Using LM Studio {settings.LMSTUDIO_MODEL} for reasoning-critical agent")
            return ChatOpenAI(
                model=settings.LMSTUDIO_MODEL,
                base_url=settings.LMSTUDIO_URL,
                api_key=settings.LMSTUDIO_API_KEY,
                temperature=0
            )
        else:
            logger.info(f"Using Ollama {settings.OLLAMA_CHAT_MODEL} for reasoning-critical agent")
            return ChatOllama(
                model=settings.OLLAMA_CHAT_MODEL,
                base_url=settings.OLLAMA_URL,
                temperature=0
            )
    
    # Default: Faster agent model (also respects LLM_PROVIDER)
    if provider == "lmstudio":
        logger.info(f"Using LM Studio {settings.LMSTUDIO_MODEL} for agent")
        return ChatOpenAI(
            model=settings.LMSTUDIO_MODEL,
            base_url=settings.LMSTUDIO_URL,
            api_key=settings.LMSTUDIO_API_KEY,
            temperature=0
        )
    else:
        logger.info(f"Using Ollama {settings.OLLAMA_AGENT_MODEL} for agent")
        return ChatOllama(
            model=settings.OLLAMA_AGENT_MODEL,
            base_url=settings.OLLAMA_URL,
            temperature=0
        )

from src.norns.tools import (
    workspace_read,
    workspace_write,
    workspace_list,
    execute_terminal_command,
)


# =============================================================================
# 1. FILE MANAGEMENT AGENT
# =============================================================================

def create_file_management_agent() -> CompiledSubAgent:
    """
    Specialist: File system operations, workspace management, file searching
    Model: Ollama (fast, local)
    Tools: workspace_read/write/list, file search, git operations
    """
    system_prompt = SUBAGENT_BASE_PROMPT + FILE_EDITING_INSTRUCTION
    llm = get_agent_llm()
    
    # Base tools
    tools = [workspace_read, workspace_write, workspace_list, execute_terminal_command]
    
    # Add Composio tools if available
    if COMPOSIO_AVAILABLE:
        try:
            composio_toolset = ComposioToolSet()
            file_tools = composio_toolset.get_tools(actions=[
                Action.FILETOOL_LIST_FILES,
                Action.FILETOOL_FIND_FILE,
            ])
            tools.extend(file_tools)
        except:
            pass  # Continue without Composio
    
    agent = create_react_agent(llm, tools=tools)
    
    return CompiledSubAgent(
        name="file_manager",
        description="""Expert in file system operations. Handles:
- Reading, writing, searching files
- Directory navigation and organization
- Git repository operations
- File permissions and ownership
Use me for any file-related tasks.""",
        runnable=agent
    )


# =============================================================================
# 2. APPLICATION INSTALLATION AGENT
# =============================================================================

def create_app_installer_agent() -> CompiledSubAgent:
    """
    Specialist: Installing packages, managing dependencies, Docker builds
    Model: Ollama
    Tools: terminal execution, package managers, Docker
    """
    llm = get_agent_llm()
    
    tools = [execute_terminal_command, workspace_read]
    
    agent = create_react_agent(llm, tools=tools)
    
    return CompiledSubAgent(
        name="app_installer",
        description="""Expert in software installation and dependency management. Handles:
- pip, npm, brew, apt package installation
- Docker image building and deployment
- Dependency resolution and version management
- Virtual environment setup
Use me to install any software or manage dependencies.""",
        runnable=agent
    )


# =============================================================================
# 3. NETWORKING AGENT
# =============================================================================

def create_networking_agent() -> CompiledSubAgent:
    """
    Specialist: Network configuration, Docker networks, DNS, routing
    Model: Ollama
    Tools: terminal, docker network commands
    """
    llm = get_agent_llm()
    
    agent = create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read]
    )
    
    return CompiledSubAgent(
        name="network_specialist",
        description="""Expert in networking and connectivity. Handles:
- Docker network creation and management
- DNS configuration (dnsmasq, /etc/hosts)
- Port allocation and conflict resolution
- Traefik/nginx routing configuration
- Network troubleshooting (ping, telnet, curl)
Use me for network-related tasks.""",
        runnable=agent
    )


# =============================================================================
# 4. SSL/TLS SECURITY AGENT
# =============================================================================

def create_security_agent() -> CompiledSubAgent:
    """
    Specialist: SSL/TLS certificates, SPIRE, cryptography
    Model: Claude Haiku (security requires better reasoning)
    Tools: terminal, SPIRE commands, certificate operations
    """
    llm = get_agent_llm(require_reasoning=True)
    
    agent = create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read, workspace_write]
    )
    
    return CompiledSubAgent(
        name="security_specialist",
        description="""Expert in security and cryptography. Handles:
- SSL/TLS certificate generation (mkcert, openssl)
- SPIRE server/agent configuration
- mTLS setup and testing
- Certificate distribution and validation
- Security policy enforcement
Use me for security, encryption, and certificate tasks.""",
        runnable=agent
    )


# =============================================================================
# 5. QA & TESTING AGENT
# =============================================================================

def create_qa_agent() -> CompiledSubAgent:
    """
    Specialist: Testing, validation, quality assurance
    Model: Ollama
    Tools: pytest, test execution, validation
    """
    llm = get_agent_llm()
    
    agent = create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read, workspace_write]
    )
    
    return CompiledSubAgent(
        name="qa_engineer",
        description="""Expert in testing and quality assurance. Handles:
- Writing and running unit tests
- Integration test execution
- API endpoint testing
- Performance benchmarking
- Validation and verification
Use me to test any component or validate functionality.""",
        runnable=agent
    )


# =============================================================================
# 6. OBSERVABILITY AGENT (Special: Listens to Everyone)
# =============================================================================

def create_observability_agent() -> CompiledSubAgent:
    """
    Specialist: Monitoring, logging, tracing - LISTENS TO ALL AGENTS
    Model: Ollama
    Tools: Log streaming, metrics queries, trace analysis
    Special: Subscribes to ALL Kafka topics to monitor the swarm
    """
    system_prompt = SUBAGENT_BASE_PROMPT + OBSERVABILITY_PROMPT + TERMINAL_COMMAND_INSTRUCTION
    llm = get_agent_llm()
    
    agent = create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read]
    )
    
    return CompiledSubAgent(
        name="observability_monitor",
        description="""Expert in monitoring and observability. Special capabilities:
- Subscribes to ALL agent coordination topics
- Streams live logs from Kafka/NATS
- Queries Prometheus metrics
- Analyzes Tempo traces
- Reports on agent health and performance
- Detects anomalies in agent behavior

Use me to:
- Monitor what all agents are doing
- Stream real-time coordination logs
- Analyze system health
- Debug agent issues
- Track performance metrics""",
        runnable=agent
    )


# =============================================================================
# 7. SSO & IDENTITY EXPERT
# =============================================================================

def create_sso_expert() -> CompiledSubAgent:
    """
    Specialist: Zitadel, OIDC, OAuth 2.1, identity management
    Model: Claude Haiku (identity is critical)
    Tools: Zitadel API, OAuth configuration
    """
    llm = get_agent_llm(require_reasoning=True)
    
    agent = create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read, workspace_write]
    )
    
    return CompiledSubAgent(
        name="sso_identity_expert",
        description="""Expert in identity and access management. Handles:
- Zitadel configuration and setup
- OAuth 2.1 client creation
- OIDC flows and JWT validation
- Service account management
- RBAC policy design
- SPIFFE ID assignment
Use me for authentication, authorization, and identity tasks.""",
        runnable=agent
    )


# =============================================================================
# 8. SCHEMA DESIGNER
# =============================================================================

def create_schema_designer() -> CompiledSubAgent:
    """
    Specialist: Database schemas, API contracts, data models
    Model: Claude Haiku (schema design needs good reasoning)
    Tools: SQL generation, Pydantic models, AsyncAPI
    """
    system_prompt = SUBAGENT_BASE_PROMPT + SCHEMA_ARCHITECT_PROMPT + FILE_EDITING_INSTRUCTION
    llm = get_agent_llm(require_reasoning=True)
    
    agent = create_react_agent(
        llm,
        tools=[workspace_read, workspace_write, execute_terminal_command]
    )
    
    return CompiledSubAgent(
        name="schema_architect",
        description="""Expert in data modeling and schema design. Handles:
- PostgreSQL table design with indexes
- Pydantic model creation
- AsyncAPI event contracts
- OpenAPI specifications
- GraphQL schemas
- Data migration scripts
Use me to design any data structure or API contract.""",
        runnable=agent
    )


# =============================================================================
# 9. COST ESTIMATOR
# =============================================================================

def create_cost_estimator() -> CompiledSubAgent:
    """
    Specialist: Cost analysis, budget forecasting, FinOps
    Model: Claude Haiku (cost analysis needs reasoning)
    Tools: Cost queries, calculator, AWS pricing API
    """
    llm = get_agent_llm(require_reasoning=True)
    
    agent = create_react_agent(
        llm,
        tools=[workspace_read, execute_terminal_command]
    )
    
    return CompiledSubAgent(
        name="cost_analyst",
        description="""Expert in cost analysis and financial operations. Handles:
- LLM cost estimation (per model, per agent)
- Infrastructure cost projection
- Budget utilization tracking
- Cost optimization recommendations
- ROI analysis for multi-model routing
- Monthly/annual cost forecasting
Use me to estimate costs or optimize spending.""",
        runnable=agent
    )


# =============================================================================
# 10. RISK MANAGER
# =============================================================================

def create_risk_manager() -> CompiledSubAgent:
    """
    Specialist: Risk assessment, security analysis, compliance checks
    Model: Claude Sonnet (risk requires deep reasoning)
    Tools: Security scanners, compliance checkers
    """
    llm = get_agent_llm(require_reasoning=True)
    
    agent = create_react_agent(
        llm,
        tools=[workspace_read, execute_terminal_command]
    )
    
    return CompiledSubAgent(
        name="risk_assessor",
        description="""Expert in risk management and security assessment. Handles:
- Security vulnerability analysis
- Risk tier classification (EU AI Act)
- Compliance gap identification (GDPR, HIPAA, BIPA)
- Threat modeling
- Disaster recovery impact analysis
- Change risk assessment (ITIL v4)
Use me to assess risks before making changes.""",
        runnable=agent
    )


# =============================================================================
# 11. GOVERNANCE AGENT
# =============================================================================

def create_governance_agent() -> CompiledSubAgent:
    """
    Specialist: Policy compliance, regulatory requirements, audit
    Model: Claude Sonnet (governance requires sophisticated reasoning)
    Tools: Policy documents, compliance frameworks
    """
    system_prompt = SUBAGENT_BASE_PROMPT + GOVERNANCE_PROMPT + MEMORY_TOOLS_INSTRUCTION
    llm = get_agent_llm(require_reasoning=True)
    
    agent = create_react_agent(
        llm,
        tools=[workspace_read, workspace_write]
    )
    
    return CompiledSubAgent(
        name="governance_officer",
        description="""Expert in governance, compliance, and regulatory requirements. Handles:
- GDPR/HIPAA compliance validation
- EU AI Act risk classification
- ITIL v4 process adherence
- Audit trail generation
- Evidence artifact collection
- DPA/BAA template review
- Policy alignment verification
Use me to ensure compliance with regulations and policies.""",
        runnable=agent
    )


# =============================================================================
# 12. PROJECT MANAGER AGENT
# =============================================================================

def create_project_manager() -> CompiledSubAgent:
    """
    Specialist: Project planning, task breakdown, coordination
    Model: Claude Sonnet (PM requires strategic thinking)
    Tools: GitHub issues, Notion, project management
    """
    llm = get_agent_llm(require_reasoning=True)
    
    tools = [workspace_read, workspace_write, execute_terminal_command]
    
    # Add Composio GitHub tools if available
    if COMPOSIO_AVAILABLE:
        try:
            composio_toolset = ComposioToolSet()
            pm_tools = composio_toolset.get_tools(actions=[
                Action.GITHUB_ISSUES_CREATE,
                Action.GITHUB_ISSUES_LIST,
            ])
            tools.extend(pm_tools)
        except:
            pass
    
    agent = create_react_agent(llm, tools=tools)
    
    return CompiledSubAgent(
        name="project_coordinator",
        description="""Expert in project management and coordination. Handles:
- Breaking down complex missions into tasks
- Creating GitHub issues and tracking progress
- Coordinating multiple agents across phases
- Risk and dependency management
- Timeline estimation
- Status reporting and documentation
Use me to plan and coordinate complex multi-agent projects.""",
        runnable=agent
    )


# =============================================================================
# ADDITIONAL SPECIALIST AGENTS
# =============================================================================

def create_documentation_agent() -> CompiledSubAgent:
    """Documentation and technical writing specialist"""
    system_prompt = SUBAGENT_BASE_PROMPT + TECHNICAL_WRITER_PROMPT + FILE_EDITING_INSTRUCTION
    llm = get_agent_llm()
    
    agent = create_react_agent(
        llm,
        tools=[workspace_read, workspace_write, workspace_list]
    )
    
    return CompiledSubAgent(
        name="technical_writer",
        description="""Expert in documentation and technical writing. Handles:
- README creation and updates
- API documentation generation
- Architecture diagrams (mermaid)
- Runbook creation
- User guides and tutorials
Use me to document anything.""",
        runnable=agent
    )


def create_devops_agent() -> CompiledSubAgent:
    """DevOps and CI/CD specialist - Uses SRE prompt"""
    system_prompt = SUBAGENT_BASE_PROMPT + SRE_PROMPT + TERMINAL_COMMAND_INSTRUCTION
    llm = get_agent_llm()
    
    tools = [execute_terminal_command, workspace_read, workspace_write]
    
    agent = create_react_agent(llm, tools=tools)
    
    return CompiledSubAgent(
        name="devops_engineer",
        description="""Expert in DevOps and CI/CD. Handles:
- Docker compose configuration
- Kubernetes manifests
- CI/CD pipeline setup
- Infrastructure as code
- Deployment automation
- GitOps workflows
Use me for deployment and automation tasks.""",
        runnable=agent
    )


def create_data_engineer() -> CompiledSubAgent:
    """Database and data pipeline specialist"""
    llm = get_agent_llm()
    
    agent = create_react_agent(
        llm,
        tools=[execute_terminal_command, workspace_read, workspace_write]
    )
    
    return CompiledSubAgent(
        name="data_engineer",
        description="""Expert in databases and data pipelines. Handles:
- PostgreSQL schema design and optimization
- Database migrations (Alembic)
- Query optimization and indexing
- Redis caching strategies
- Data pipeline design (Kafka/NATS)
- ETL processes
Use me for database and data-related tasks.""",
        runnable=agent
    )


# =============================================================================
# SUBAGENT REGISTRY
# =============================================================================

def create_all_specialized_agents() -> list[CompiledSubAgent]:
    """
    Create all specialized subagents for the Norns deep agent.
    
    Returns a list of CompiledSubAgent instances that can be passed
    to create_deep_agent().
    """
    return [
        # Core infrastructure specialists
        create_file_management_agent(),          # 1. Files
        create_app_installer_agent(),            # 2. Installation
        create_networking_agent(),               # 3. Networking
        create_security_agent(),                 # 4. SSL/TLS
        create_qa_agent(),                       # 5. QA/Testing
        create_observability_agent(),            # 6. Monitoring (listens to all)
        
        # Governance & management
        create_sso_expert(),                     # 7. Identity/SSO
        create_schema_designer(),                # 8. Schema design
        create_cost_estimator(),                 # 9. Cost analysis
        create_risk_manager(),                   # 10. Risk assessment
        create_governance_agent(),               # 11. Compliance
        create_project_manager(),                # 12. PM/coordination
        
        # Additional specialists
        create_documentation_agent(),            # 13. Documentation
        create_devops_agent(),                   # 14. DevOps
        create_data_engineer(),                  # 15. Data/DB
    ]


def get_subagent_catalog() -> dict[str, str]:
    """
    Get a human-readable catalog of all available subagents.
    Useful for displaying in UI or debugging.
    """
    return {
        "file_manager": "File system operations, workspace management, git",
        "app_installer": "Package installation, Docker builds, dependencies",
        "network_specialist": "Docker networks, DNS, routing, Traefik",
        "security_specialist": "SSL/TLS certificates, SPIRE, mTLS, security",
        "qa_engineer": "Testing, validation, quality assurance",
        "observability_monitor": "Monitoring all agents, log streaming, metrics",
        "sso_identity_expert": "Zitadel, OAuth 2.1, OIDC, identity management",
        "schema_architect": "Database schemas, API contracts, data models",
        "cost_analyst": "Cost estimation, budget forecasting, FinOps",
        "risk_assessor": "Risk analysis, security assessment, threat modeling",
        "governance_officer": "Compliance, regulatory requirements, audit",
        "project_coordinator": "Project planning, task breakdown, GitHub issues",
        "technical_writer": "Documentation, README, runbooks",
        "devops_engineer": "CI/CD, deployments, infrastructure as code",
        "data_engineer": "Databases, data pipelines, ETL, optimization",
    }

