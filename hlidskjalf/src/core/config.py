from typing import Optional
"""
Hliðskjálf - Odin's High Seat
The throne from which all Nine Realms are observed.

Platform control plane configuration for:
- Port registry and auto-assignment
- Deployment management across realms (dev/staging/prod)
- Health monitoring via Huginn (real-time) and Muninn (historical)
- Nginx configuration generation
- SPIRE/zero-trust orchestration
"""

from functools import lru_cache
from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Hliðskjálf settings - the all-seeing throne configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ==========================================================================
    # Application Settings
    # ==========================================================================
    APP_NAME: str = "Hliðskjálf"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="The realm: midgard(dev)/alfheim(staging)/asgard(prod)")
    DEBUG: bool = Field(default=True)
    
    # ==========================================================================
    # Server Settings
    # ==========================================================================
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8900)
    
    # ==========================================================================
    # Database - The Well of Mímir (wisdom/knowledge store)
    # Uses Docker service name 'postgres' when in container, localhost for local dev
    # ==========================================================================
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://ravenhelm:ravenhelm@postgres:5432/hlidskjalf"
    )
    POSTGRES_URL: str = Field(
        default="postgresql://postgres:postgres@postgres:5432/postgres",
        description="Standard postgres URL for Muninn memory"
    )
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)
    
    # ==========================================================================
    # Redis - Caching & Pub/Sub for real-time updates
    # Uses Docker service name 'redis' when in container
    # ==========================================================================
    REDIS_URL: RedisDsn = Field(default="redis://redis:6379/1")
    REDIS_MEMORY_TTL_SECONDS: int = Field(
        default=3600,
        description="TTL for cached chat state and TODO metadata",
    )
    REDIS_MEMORY_PREFIX: str = Field(
        default="norns",
        description="Key prefix for Redis short-term memory",
    )
    
    # ==========================================================================
    # Port Registry Settings
    # ==========================================================================
    PORT_RANGE_HTTP_START: int = Field(default=8000, description="Start of HTTP port range")
    PORT_RANGE_HTTP_END: int = Field(default=8999, description="End of HTTP port range")
    PORT_RANGE_HTTPS_START: int = Field(default=8400, description="Start of HTTPS port range")
    PORT_RANGE_HTTPS_END: int = Field(default=8599, description="End of HTTPS port range")
    PORT_RANGE_GRPC_START: int = Field(default=9000, description="Start of gRPC port range")
    PORT_RANGE_GRPC_END: int = Field(default=9199, description="End of gRPC port range")
    PORT_RANGE_METRICS_START: int = Field(default=9200, description="Start of metrics port range")
    PORT_RANGE_METRICS_END: int = Field(default=9299, description="End of metrics port range")
    
    # Reserved ports that should never be auto-assigned
    RESERVED_PORTS: list[int] = Field(default=[
        80, 443,          # HTTP/HTTPS
        5432,             # PostgreSQL
        6379,             # Redis
        4222, 8222,       # NATS
        9092,             # Kafka/Redpanda
        8200,             # OpenBao/Vault
        4566,             # LocalStack
        4317, 4318,       # OTEL
        9090,             # Prometheus
        3100,             # Loki
        3200,             # Tempo
        3000,             # Grafana
        9093,             # Alertmanager
        8081,             # SPIRE Server
    ])
    
    # ==========================================================================
    # Deployment Targets
    # ==========================================================================
    LOCAL_DOCKER_SOCKET: str = Field(default="/var/run/docker.sock")
    
    # AWS Settings for cloud deployments
    AWS_REGION: str = Field(default="us-east-1")
    AWS_ENDPOINT_URL: Optional[str] = Field(default=None, description="LocalStack endpoint for dev")
    
    # ==========================================================================
    # SPIRE / Zero-Trust Settings
    # ==========================================================================
    SPIRE_AGENT_SOCKET: str = Field(default="/tmp/spire-agent/public/api.sock")
    TRUST_DOMAIN: str = Field(default="ravenhelm.local")
    
    # ==========================================================================
    # Nginx Config Generation
    # ==========================================================================
    NGINX_CONFIG_PATH: str = Field(default="/etc/nginx/conf.d")
    NGINX_TEMPLATE_PATH: str = Field(default="./config/nginx-templates")
    RAVENHELM_PROXY_CONFIG: str = Field(default="/config/nginx.conf")
    
    # ==========================================================================
    # Health Check Settings
    # ==========================================================================
    HEALTH_CHECK_INTERVAL_SECONDS: int = Field(default=30)
    HEALTH_CHECK_TIMEOUT_SECONDS: int = Field(default=10)
    UNHEALTHY_THRESHOLD: int = Field(default=3)
    
    # ==========================================================================
    # Observability
    # Uses Docker service name 'otel-collector' when in container
    # ==========================================================================
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(default="http://otel-collector:4317")
    OTEL_SERVICE_NAME: str = Field(default="ravenhelm-control")
    PROMETHEUS_METRICS_PATH: str = Field(default="/metrics")
    
    # ==========================================================================
    # Platform Services URLs (ravenhelm.test domains via Traefik)
    # ==========================================================================
    GITLAB_URL: str = Field(default="https://gitlab.ravenhelm.test:8443")
    GRAFANA_URL: str = Field(default="https://grafana.observe.ravenhelm.test:8443")
    PROMETHEUS_URL: str = Field(default="https://prometheus.observe.ravenhelm.test:8443")
    
    # ==========================================================================
    # THE NORNS - AI Agent Configuration
    # ==========================================================================
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key for the Norns")
    NORNS_MODEL: str = Field(default="gpt-4o", description="Model for the Norns agent")
    NORNS_TEMPERATURE: float = Field(default=0.7, description="Creativity level for Norse flavor")
    NORNS_GRAPH_API_URL: str = Field(
        default="https://norns.ravenhelm.test:8443",
        description="Base URL for the LangGraph runtime powering the Norns",
    )
    NORNS_GRAPH_ASSISTANT_ID: str = Field(
        default="norns",
        description="Graph/assistant identifier exposed to the Agent Chat UI",
    )
    
    # ==========================================================================
    # Ollama - Local LLM for cognitive architecture
    # ==========================================================================
    OLLAMA_URL: str = Field(
        default="http://ollama:11434",
        description="Ollama API URL (Docker service name)"
    )
    OLLAMA_EMBEDDING_MODEL: str = Field(
        default="nomic-embed-text",
        description="Model for generating embeddings"
    )
    OLLAMA_CHAT_MODEL: str = Field(
        default="mistral-nemo:latest",
        description="Model for main Norns chat (12B, good reasoning)"
    )
    OLLAMA_AGENT_MODEL: str = Field(
        default="mistral:latest",
        description="Model for specialized agents (7B, faster)"
    )
    
    # ==========================================================================
    # HuggingFace TGI - Alternative local LLM provider
    # ==========================================================================
    HUGGINGFACE_TGI_URL: str = Field(
        default="http://hf-reasoning:80",
        description="HuggingFace TGI API URL for main reasoning model"
    )
    HUGGINGFACE_TGI_AGENTS_URL: str = Field(
        default="http://hf-agents:80",
        description="HuggingFace TGI API URL for specialized agents"
    )
    HUGGING_FACE_HUB_TOKEN: str = Field(
        default="",
        description="HuggingFace Hub token for gated models"
    )
    LLM_PROVIDER: str = Field(
        default="ollama",
        description="LLM provider: 'ollama', 'lmstudio', 'huggingface', 'openai'"
    )
    
    # ==========================================================================
    # LM Studio - Local model server with OpenAI-compatible API
    # ==========================================================================
    LMSTUDIO_URL: str = Field(
        default="http://host.docker.internal:1234/v1",
        description="LM Studio API URL (use host.docker.internal from Docker)"
    )
    LMSTUDIO_MODEL: str = Field(
        default="ministral-3-14b-reasoning",
        description="Model loaded in LM Studio"
    )
    
    # LangFuse for tracing the Norns' thoughts
    LANGFUSE_HOST: str = Field(default="https://langfuse.observe.ravenhelm.test")
    LANGFUSE_PUBLIC_KEY: str = Field(default="")
    LANGFUSE_SECRET_KEY: str = Field(default="")

    # ==========================================================================
    # Notifications - Twilio
    # ==========================================================================
    TWILIO_ACCOUNT_SID: str = Field(default="", description="Twilio Account SID for SMS alerts")
    TWILIO_AUTH_TOKEN: str = Field(default="", description="Twilio Auth Token for SMS alerts")
    TWILIO_FROM_NUMBER: str = Field(default="", description="E.164 number registered with Twilio")
    TWILIO_MESSAGING_SERVICE_SID: str = Field(
        default="",
        description="Optional Messaging Service SID (preferred when available)",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()

