from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import api_keys, audit_logs, auth, authz, health, organizations, users
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.db import init_db, close_db
from app.core.cache import init_redis, close_redis
from app.core.kafka import init_kafka, close_kafka
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)
from app.authz.client import ensure_store_and_model, close_client as close_openfga

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("Starting application", service=settings.SERVICE_NAME, env=settings.ENVIRONMENT)

    await init_db()
    await init_redis()
    await init_kafka()

    # Initialize OpenFGA store and model
    try:
        await ensure_store_and_model()
        logger.info("OpenFGA initialized")
    except Exception as e:
        logger.warning("OpenFGA initialization failed (may not be running)", error=str(e))

    yield

    logger.info("Shutting down application")
    await close_openfga()
    await close_kafka()
    await close_redis()
    await close_db()


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    logger.warning(
        "Rate limit exceeded",
        client_ip=get_remote_address(request),
        path=request.url.path,
        limit=str(exc.detail),
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.SERVICE_NAME,
        description="Backend service template",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Store limiter in app state
    app.state.limiter = limiter

    # Add rate limit exception handler
    if settings.RATE_LIMIT_ENABLED:
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Middleware stack (order matters - first added = last executed)
    # 1. Security headers (outermost - runs last on response)
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. Request logging (logs all requests with timing)
    app.add_middleware(RequestLoggingMiddleware)

    # 3. Request ID (adds X-Request-ID for tracing)
    app.add_middleware(RequestIDMiddleware)

    # 4. Trusted hosts (production security - reject unknown hosts)
    if settings.ENVIRONMENT == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # 5. CORS (innermost - runs first on request)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        max_age=3600,  # Cache preflight for 1 hour
    )

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, tags=["auth"])
    app.include_router(authz.router, tags=["authorization"])
    app.include_router(users.router, tags=["users"])
    app.include_router(api_keys.router, tags=["api-keys"])
    app.include_router(organizations.router, tags=["organizations"])
    app.include_router(audit_logs.router, tags=["audit-logs"])

    # Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # OpenTelemetry instrumentation
    if OTEL_AVAILABLE and settings.OTEL_ENABLED:
        FastAPIInstrumentor.instrument_app(app)

    logger.info(
        "Application created",
        environment=settings.ENVIRONMENT,
        cors_origins=settings.CORS_ORIGINS,
        rate_limit_enabled=settings.RATE_LIMIT_ENABLED,
    )

    return app


app = create_app()
