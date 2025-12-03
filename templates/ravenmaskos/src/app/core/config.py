from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    SERVICE_NAME: str = "ravenmaskos"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Deployment Mode
    # - shared: Uses shared platform services (gitlab-sre stack)
    # - standalone: Self-contained with local services
    DEPLOYMENT_MODE: Literal["shared", "standalone"] = "standalone"
    
    # Ravenhelm Platform (shared mode)
    # When DEPLOYMENT_MODE=shared, services connect to the central platform
    RAVENHELM_DOMAIN: str = "ravenhelm.test"  # Base domain for platform services

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS - MUST be explicitly configured per environment
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]  # Default to local frontend only
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "X-Request-ID"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Trusted Hosts (production security)
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"  # Default rate limit
    RATE_LIMIT_BURST: str = "20/second"  # Burst limit

    # PostgreSQL
    # For local dev: use DATABASE_URL directly
    # For production: set DB_SECRET_NAME to fetch credentials from Secrets Manager
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    DATABASE_READ_URL: str | None = None  # Optional read replica
    DB_SECRET_NAME: str | None = None  # AWS Secrets Manager secret name
    DB_HOST: str = "localhost"  # Used when building URL from secrets
    DB_PORT: int = 5432
    DB_NAME: str = "app"
    DB_SSL_MODE: str = "prefer"  # disable, prefer, require, verify-ca, verify-full
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10
    # TLS settings for Redis
    REDIS_SSL: bool = False  # Enable TLS
    REDIS_SSL_CERT_REQS: str = "required"  # none, optional, required
    REDIS_SSL_CA_CERTS: str | None = None  # Path to CA certificate file
    REDIS_SSL_CERTFILE: str | None = None  # Path to client certificate
    REDIS_SSL_KEYFILE: str | None = None  # Path to client private key

    # =========================================================================
    # HUGINN - State Manager (fast, low-latency state transport)
    # =========================================================================
    # NATS JetStream for real-time state deltas, turn updates, voice events
    NATS_URL: str = "nats://localhost:4222"
    NATS_CONNECT_TIMEOUT: int = 5
    NATS_MAX_RECONNECT_ATTEMPTS: int = 10
    # JetStream settings
    NATS_JS_DOMAIN: str | None = None  # JetStream domain (for leaf nodes)
    NATS_JS_PREFIX: str = "ravenhelm"  # Stream name prefix
    
    # Huginn streams (turn-level, session-level state)
    HUGINN_TURN_STREAM: str = "HUGINN_TURNS"
    HUGINN_SESSION_STREAM: str = "HUGINN_SESSIONS"
    HUGINN_VOICE_STREAM: str = "HUGINN_VOICE"

    # =========================================================================
    # MUNINN - Memory Manager (durable event streaming for memory consolidation)
    # =========================================================================
    # Kafka/Redpanda for memory candidates, reinforcement, domain ingestion
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CONSUMER_GROUP: str = "ravenmaskos-group"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"
    # TLS settings for Kafka
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"  # PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
    KAFKA_SSL_CAFILE: str | None = None  # Path to CA certificate
    KAFKA_SSL_CERTFILE: str | None = None  # Path to client certificate
    KAFKA_SSL_KEYFILE: str | None = None  # Path to client private key
    KAFKA_SSL_PASSWORD: str | None = None  # Password for client private key
    # SASL settings (for SASL_PLAINTEXT or SASL_SSL)
    KAFKA_SASL_MECHANISM: str | None = None  # PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
    KAFKA_SASL_USERNAME: str | None = None
    KAFKA_SASL_PASSWORD: str | None = None
    
    # Muninn topics (memory events, consolidation signals)
    MUNINN_MEMORY_CANDIDATE_TOPIC: str = "muninn.memory.candidate"
    MUNINN_MEMORY_PROMOTED_TOPIC: str = "muninn.memory.promoted"
    MUNINN_REINFORCEMENT_TOPIC: str = "muninn.reinforcement"
    MUNINN_DOMAIN_INGESTION_TOPIC: str = "muninn.domain.ingestion"

    @field_validator("KAFKA_BOOTSTRAP_SERVERS", mode="before")
    @classmethod
    def parse_kafka_servers(cls, v: str | list[str]) -> str:
        if isinstance(v, list):
            return ",".join(v)
        return v

    # Security - Legacy JWT (deprecated, use Zitadel)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Zitadel OIDC
    ZITADEL_ISSUER: str = "http://localhost:8085"
    ZITADEL_PROJECT_ID: str | None = None
    ZITADEL_WEB_CLIENT_ID: str | None = None
    ZITADEL_API_CLIENT_ID: str | None = None
    ZITADEL_API_CLIENT_SECRET: str | None = None
    ZITADEL_JWKS_CACHE_TTL: int = 3600  # Cache JWKS for 1 hour

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_ENDPOINT_URL: str | None = None  # For LocalStack

    # =========================================================================
    # Observability - Infrastructure Telemetry
    # =========================================================================
    OTEL_ENABLED: bool = True
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "ravenmaskos"

    # Prometheus
    PROMETHEUS_ENABLED: bool = True

    # =========================================================================
    # LLM Observability - LangFuse (LangGraph/LangChain tracing)
    # =========================================================================
    LANGFUSE_ENABLED: bool = True
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "http://localhost:3001"  # Self-hosted
    # For shared mode: https://langfuse.observe.ravenhelm.test

    # Phoenix (Arize) - Embeddings & RAG debugging (optional)
    PHOENIX_ENABLED: bool = False
    PHOENIX_HOST: str = "http://localhost:6006"
    # For shared mode: https://phoenix.observe.ravenhelm.test

    # OpenFGA Authorization
    OPENFGA_API_URL: str = "http://localhost:8080"
    OPENFGA_STORE_NAME: str = "ravenmaskos"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
