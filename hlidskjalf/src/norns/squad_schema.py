"""
Squad Messaging Schema for Multi-Agent Coordination via Redpanda

This module defines the event-driven architecture for agent collaboration.
Each agent publishes events to Redpanda topics and subscribes to relevant topics
to coordinate work on platform deployment.
"""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AgentRole(str, Enum):
    """Agent specializations in the squad"""
    ORCHESTRATOR = "orchestrator"  # The Norns - coordinates all agents
    CERT_AGENT = "cert_agent"  # Manages SSL certificates
    DOCKER_AGENT = "docker_agent"  # Manages Docker containers
    ENV_AGENT = "env_agent"  # Manages .env files and configuration
    PROXY_AGENT = "proxy_agent"  # Manages ravenhelm-proxy
    DATABASE_AGENT = "database_agent"  # Manages PostgreSQL
    CACHE_AGENT = "cache_agent"  # Manages Redis/NATS
    EVENTS_AGENT = "events_agent"  # Manages Redpanda
    SECRETS_AGENT = "secrets_agent"  # Manages OpenBao
    OBSERVABILITY_AGENT = "observability_agent"  # Manages Grafana/Prometheus/etc
    RAG_AGENT = "rag_agent"  # Manages Weaviate/embeddings/docling
    GRAPH_AGENT = "graph_agent"  # Manages Neo4j/Memgraph
    HLIDSKJALF_AGENT = "hlidskjalf_agent"  # Manages control plane API/UI


class EventType(str, Enum):
    """Event types for agent communication"""
    # Task events
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    
    # State change events
    SERVICE_STARTING = "service_starting"
    SERVICE_READY = "service_ready"
    SERVICE_UNHEALTHY = "service_unhealthy"
    SERVICE_STOPPED = "service_stopped"
    
    # Dependency events
    DEPENDENCY_REQUIRED = "dependency_required"
    DEPENDENCY_SATISFIED = "dependency_satisfied"
    
    # Coordination events
    REQUEST_STATUS = "request_status"
    STATUS_REPORT = "status_report"
    SQUAD_READY = "squad_ready"


class AgentEvent(BaseModel):
    """Base event structure for all agent communication"""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of event")
    source_agent: AgentRole = Field(..., description="Agent that emitted this event")
    target_agent: Optional[AgentRole] = Field(None, description="Specific target agent, or None for broadcast")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = Field(None, description="Links related events together")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")


class TaskAssignment(BaseModel):
    """Task assignment payload"""
    task_id: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    parameters: dict[str, Any] = Field(default_factory=dict)


class TaskProgress(BaseModel):
    """Task progress update payload"""
    task_id: str
    percent_complete: int = Field(..., ge=0, le=100)
    message: str
    substeps_completed: int = 0
    substeps_total: int = 0


class ServiceStatus(BaseModel):
    """Service health status payload"""
    service_name: str
    status: str  # starting, ready, unhealthy, stopped
    container_id: Optional[str] = None
    health_check_url: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyRequest(BaseModel):
    """Dependency requirement payload"""
    requesting_agent: AgentRole
    dependency_type: str  # e.g., "certificate", "database_ready", "port_allocated"
    dependency_name: str
    required_by: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


# Redpanda Topics
class Topics:
    """Redpanda topic names for agent communication"""
    # Main coordination topic
    SQUAD_COORDINATION = "ravenhelm.squad.coordination"
    
    # Service-specific topics
    CERTS = "ravenhelm.squad.certs"
    DOCKER = "ravenhelm.squad.docker"
    ENV_CONFIG = "ravenhelm.squad.config"
    PROXY = "ravenhelm.squad.proxy"
    DATABASE = "ravenhelm.squad.database"
    CACHE = "ravenhelm.squad.cache"
    EVENTS = "ravenhelm.squad.events"
    SECRETS = "ravenhelm.squad.secrets"
    OBSERVABILITY = "ravenhelm.squad.observability"
    RAG = "ravenhelm.squad.rag"
    GRAPH = "ravenhelm.squad.graph"
    HLIDSKJALF = "ravenhelm.squad.hlidskjalf"
    
    # Status and health
    HEALTH_STATUS = "ravenhelm.squad.health"
    TASK_STATUS = "ravenhelm.squad.tasks"


# Agent-to-Topic Mapping
AGENT_TOPICS = {
    AgentRole.ORCHESTRATOR: [Topics.SQUAD_COORDINATION],
    AgentRole.CERT_AGENT: [Topics.CERTS, Topics.SQUAD_COORDINATION],
    AgentRole.DOCKER_AGENT: [Topics.DOCKER, Topics.SQUAD_COORDINATION],
    AgentRole.ENV_AGENT: [Topics.ENV_CONFIG, Topics.SQUAD_COORDINATION],
    AgentRole.PROXY_AGENT: [Topics.PROXY, Topics.SQUAD_COORDINATION],
    AgentRole.DATABASE_AGENT: [Topics.DATABASE, Topics.SQUAD_COORDINATION],
    AgentRole.CACHE_AGENT: [Topics.CACHE, Topics.SQUAD_COORDINATION],
    AgentRole.EVENTS_AGENT: [Topics.EVENTS, Topics.SQUAD_COORDINATION],
    AgentRole.SECRETS_AGENT: [Topics.SECRETS, Topics.SQUAD_COORDINATION],
    AgentRole.OBSERVABILITY_AGENT: [Topics.OBSERVABILITY, Topics.SQUAD_COORDINATION],
    AgentRole.RAG_AGENT: [Topics.RAG, Topics.SQUAD_COORDINATION],
    AgentRole.GRAPH_AGENT: [Topics.GRAPH, Topics.SQUAD_COORDINATION],
    AgentRole.HLIDSKJALF_AGENT: [Topics.HLIDSKJALF, Topics.SQUAD_COORDINATION],
}


# Agent specialization prompts
AGENT_PROMPTS = {
    AgentRole.CERT_AGENT: """You are the Certificate Agent. Your responsibility:
- Copy SSL certificates from ravenhelm-proxy/config/certs/ to config/certs/
- Verify certificate validity and SANs
- Emit SERVICE_READY when certificates are distributed
Dependencies: None (you run first!)""",

    AgentRole.PROXY_AGENT: """You are the Proxy Agent. Your responsibility:
- Start ravenhelm-proxy container (cd ravenhelm-proxy && docker compose up -d)
- Verify nginx configuration
- Emit SERVICE_READY when proxy is routing traffic
Dependencies: CERT_AGENT must be ready""",

    AgentRole.ENV_AGENT: """You are the Environment Agent. Your responsibility:
- Check for .env file in workspace root
- Validate required keys (OPENAI_API_KEY, etc.)
- Report missing/invalid configuration
- Emit SERVICE_READY when environment is configured
Dependencies: None""",

    AgentRole.DATABASE_AGENT: """You are the Database Agent. Your responsibility:
- Ensure PostgreSQL is running and healthy
- Verify Muninn schema exists
- Check LangFuse database initialization
- Emit SERVICE_READY when database is operational
Dependencies: None (already running)""",

    AgentRole.CACHE_AGENT: """You are the Cache Agent (Huginn Layer). Your responsibility:
- Start Redis and NATS JetStream (docker compose up -d redis nats)
- Verify both services are healthy
- Emit SERVICE_READY when Huginn layer is operational
Dependencies: None""",

    AgentRole.EVENTS_AGENT: """You are the Events Agent (Muninn Layer). Your responsibility:
- Ensure Redpanda is healthy
- Start redpanda-console and events-nginx (docker compose up -d redpanda-console events-nginx)
- Emit SERVICE_READY when Muninn event layer is operational
Dependencies: PROXY_AGENT must be ready""",

    AgentRole.SECRETS_AGENT: """You are the Secrets Agent. Your responsibility:
- Verify OpenBao is running
- Check initialization keys in openbao/init-keys.json
- Start vault-nginx if needed
- Emit SERVICE_READY when secrets management is operational
Dependencies: PROXY_AGENT must be ready""",

    AgentRole.OBSERVABILITY_AGENT: """You are the Observability Agent. Your responsibility:
- Verify Grafana, Prometheus, Loki, Tempo are running
- Fix LangFuse and observe-nginx restart issues
- Verify Phoenix is accessible
- Emit SERVICE_READY when observability stack is operational
Dependencies: DATABASE_AGENT (for LangFuse), PROXY_AGENT""",

    AgentRole.RAG_AGENT: """You are the RAG Pipeline Agent. Your responsibility:
- Start embeddings service (docker compose up -d embeddings)
- Wait for model download, then start Weaviate, reranker, docling
- Verify all services are healthy
- Emit SERVICE_READY when RAG pipeline is operational
Dependencies: None""",

    AgentRole.GRAPH_AGENT: """You are the Graph Database Agent. Your responsibility:
- Start Memgraph and Neo4j (docker compose up -d memgraph neo4j)
- Verify both graph databases are healthy
- Emit SERVICE_READY when graph layer is operational
Dependencies: None""",

    AgentRole.HLIDSKJALF_AGENT: """You are the Hlidskjalf Control Plane Agent. Your responsibility:
- Build and start hlidskjalf API and UI (docker compose up -d --build hlidskjalf hlidskjalf-ui)
- Verify both services are healthy
- Test API endpoints
- Emit SERVICE_READY when control plane is operational
Dependencies: DATABASE_AGENT, CACHE_AGENT, EVENTS_AGENT, PROXY_AGENT""",

    AgentRole.DOCKER_AGENT: """You are the Docker Agent. Your responsibility:
- Monitor docker compose ps output
- Report container health status
- Restart unhealthy containers if needed
- Emit status updates on health changes
Dependencies: None (monitoring role)""",
}


# Deployment order (based on dependencies)
DEPLOYMENT_ORDER = [
    # Phase 1: Prerequisites
    [AgentRole.CERT_AGENT, AgentRole.ENV_AGENT, AgentRole.DATABASE_AGENT],
    
    # Phase 2: Core infrastructure
    [AgentRole.PROXY_AGENT, AgentRole.CACHE_AGENT, AgentRole.SECRETS_AGENT],
    
    # Phase 3: Event layer and monitoring
    [AgentRole.EVENTS_AGENT, AgentRole.OBSERVABILITY_AGENT, AgentRole.DOCKER_AGENT],
    
    # Phase 4: Data layers
    [AgentRole.RAG_AGENT, AgentRole.GRAPH_AGENT],
    
    # Phase 5: Control plane
    [AgentRole.HLIDSKJALF_AGENT],
]

