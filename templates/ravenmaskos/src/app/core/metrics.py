"""Custom Prometheus metrics for observability.

Provides application-specific metrics for:
- Request latency and throughput
- AI/LLM usage and costs
- Database and cache performance
- Business metrics (users, orgs, etc.)
- Error tracking
"""

from functools import wraps
from typing import Any, Callable
import time

from prometheus_client import Counter, Gauge, Histogram, Summary, Info

from app.core.config import settings

# =============================================================================
# Application Info
# =============================================================================

APP_INFO = Info(
    "app",
    "Application information",
)
APP_INFO.info({
    "service": settings.SERVICE_NAME,
    "environment": settings.ENVIRONMENT,
    "version": "0.1.0",
})

# =============================================================================
# HTTP Request Metrics
# =============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUEST_SIZE_BYTES = Summary(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
)

HTTP_RESPONSE_SIZE_BYTES = Summary(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "endpoint"],
)

# =============================================================================
# AI/LLM Metrics
# =============================================================================

LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total number of LLM API requests",
    ["provider", "model", "org_id", "status"],
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total number of tokens processed",
    ["provider", "model", "org_id", "direction"],  # direction: input/output
)

LLM_COST_USD_TOTAL = Counter(
    "llm_cost_usd_total",
    "Total LLM cost in USD (scaled by 10000 for precision)",
    ["provider", "model", "org_id"],
)

LLM_REQUEST_DURATION_SECONDS = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

LLM_FIRST_TOKEN_DURATION_SECONDS = Histogram(
    "llm_first_token_duration_seconds",
    "Time to first token in seconds (streaming)",
    ["provider", "model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# =============================================================================
# Agent Metrics
# =============================================================================

AGENT_EXECUTIONS_TOTAL = Counter(
    "agent_executions_total",
    "Total number of agent executions",
    ["agent_type", "org_id", "status"],
)

AGENT_TOOL_CALLS_TOTAL = Counter(
    "agent_tool_calls_total",
    "Total number of tool calls by agents",
    ["agent_type", "tool_name", "org_id", "status"],
)

AGENT_EXECUTION_DURATION_SECONDS = Histogram(
    "agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["agent_type"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
)

AGENT_ACTIVE_EXECUTIONS = Gauge(
    "agent_active_executions",
    "Number of active agent executions",
    ["agent_type", "org_id"],
)

# =============================================================================
# Database Metrics
# =============================================================================

DB_CONNECTIONS_TOTAL = Gauge(
    "db_connections_total",
    "Total number of database connections in pool",
    ["pool"],  # primary/replica
)

DB_CONNECTIONS_AVAILABLE = Gauge(
    "db_connections_available",
    "Number of available database connections",
    ["pool"],
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # select/insert/update/delete
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
)

DB_ERRORS_TOTAL = Counter(
    "db_errors_total",
    "Total number of database errors",
    ["operation", "error_type"],
)

# =============================================================================
# Cache Metrics
# =============================================================================

CACHE_OPERATIONS_TOTAL = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    ["operation", "status"],  # operation: get/set/delete, status: hit/miss/error
)

CACHE_OPERATION_DURATION_SECONDS = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
)

# =============================================================================
# Kafka Metrics
# =============================================================================

KAFKA_MESSAGES_PRODUCED_TOTAL = Counter(
    "kafka_messages_produced_total",
    "Total number of Kafka messages produced",
    ["topic", "status"],
)

KAFKA_MESSAGES_CONSUMED_TOTAL = Counter(
    "kafka_messages_consumed_total",
    "Total number of Kafka messages consumed",
    ["topic", "consumer_group", "status"],
)

KAFKA_PRODUCE_DURATION_SECONDS = Histogram(
    "kafka_produce_duration_seconds",
    "Kafka produce duration in seconds",
    ["topic"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

# =============================================================================
# Business Metrics
# =============================================================================

ACTIVE_ORGANIZATIONS = Gauge(
    "active_organizations",
    "Number of active organizations",
    ["tier"],
)

ACTIVE_USERS = Gauge(
    "active_users",
    "Number of active users",
    ["org_id"],
)

API_KEYS_ACTIVE = Gauge(
    "api_keys_active",
    "Number of active API keys",
    ["org_id"],
)

# =============================================================================
# Error Metrics
# =============================================================================

ERRORS_TOTAL = Counter(
    "errors_total",
    "Total number of errors",
    ["error_type", "component"],
)

UNHANDLED_EXCEPTIONS_TOTAL = Counter(
    "unhandled_exceptions_total",
    "Total number of unhandled exceptions",
    ["exception_type", "endpoint"],
)

# =============================================================================
# Rate Limiting Metrics
# =============================================================================

RATE_LIMIT_EXCEEDED_TOTAL = Counter(
    "rate_limit_exceeded_total",
    "Total number of rate limit exceeded events",
    ["endpoint", "org_id"],
)

# =============================================================================
# Helper Functions and Decorators
# =============================================================================


def observe_http_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """Record HTTP request metrics."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method, endpoint=endpoint, status_code=str(status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(
        duration
    )


def observe_llm_request(
    provider: str,
    model: str,
    org_id: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    duration: float,
    status: str = "success",
) -> None:
    """Record LLM request metrics."""
    LLM_REQUESTS_TOTAL.labels(
        provider=provider, model=model, org_id=org_id, status=status
    ).inc()

    LLM_TOKENS_TOTAL.labels(
        provider=provider, model=model, org_id=org_id, direction="input"
    ).inc(input_tokens)

    LLM_TOKENS_TOTAL.labels(
        provider=provider, model=model, org_id=org_id, direction="output"
    ).inc(output_tokens)

    # Scale cost by 10000 for counter precision (cents * 100)
    LLM_COST_USD_TOTAL.labels(provider=provider, model=model, org_id=org_id).inc(
        int(cost_usd * 10000)
    )

    LLM_REQUEST_DURATION_SECONDS.labels(provider=provider, model=model).observe(
        duration
    )


def observe_agent_execution(
    agent_type: str,
    org_id: str,
    duration: float,
    status: str = "success",
) -> None:
    """Record agent execution metrics."""
    AGENT_EXECUTIONS_TOTAL.labels(
        agent_type=agent_type, org_id=org_id, status=status
    ).inc()
    AGENT_EXECUTION_DURATION_SECONDS.labels(agent_type=agent_type).observe(duration)


def observe_tool_call(
    agent_type: str,
    tool_name: str,
    org_id: str,
    status: str = "success",
) -> None:
    """Record agent tool call metrics."""
    AGENT_TOOL_CALLS_TOTAL.labels(
        agent_type=agent_type, tool_name=tool_name, org_id=org_id, status=status
    ).inc()


def timed(metric: Histogram, **labels: str) -> Callable:
    """Decorator to time a function and observe with a histogram.

    Usage:
        @timed(DB_QUERY_DURATION_SECONDS, operation="select")
        async def fetch_users():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                metric.labels(**labels).observe(duration)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                metric.labels(**labels).observe(duration)

        if hasattr(func, "__await__"):
            return async_wrapper
        return sync_wrapper

    return decorator


def counted(metric: Counter, **labels: str) -> Callable:
    """Decorator to count function calls.

    Usage:
        @counted(CACHE_OPERATIONS_TOTAL, operation="get")
        async def cache_get(key):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = await func(*args, **kwargs)
                metric.labels(**labels, status="success").inc()
                return result
            except Exception:
                metric.labels(**labels, status="error").inc()
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = func(*args, **kwargs)
                metric.labels(**labels, status="success").inc()
                return result
            except Exception:
                metric.labels(**labels, status="error").inc()
                raise

        if hasattr(func, "__await__"):
            return async_wrapper
        return sync_wrapper

    return decorator
