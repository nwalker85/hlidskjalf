"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██╗  ██╗██╗     ██╗██████╗ ███████╗██╗  ██╗     ██╗ █████╗ ██╗     ███████╗║
║     ██║  ██║██║     ██║██╔══██╗██╔════╝██║ ██╔╝     ██║██╔══██╗██║     ██╔════╝║
║     ███████║██║     ██║██║  ██║███████╗█████╔╝      ██║███████║██║     █████╗  ║
║     ██╔══██║██║     ██║██║  ██║╚════██║██╔═██╗ ██   ██║██╔══██║██║     ██╔══╝  ║
║     ██║  ██║███████╗██║██████╔╝███████║██║  ██╗╚█████╔╝██║  ██║███████╗██║     ║
║     ╚═╝  ╚═╝╚══════╝╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝╚══════╝╚═╝     ║
║                                                                               ║
║                         Odin's High Seat                                      ║
║              The throne from which all Nine Realms are observed               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

From Hliðskjálf, the All-Father observes:
  • Midgard (development) - where mortals build
  • Alfheim (staging) - where light elves test  
  • Asgard (production) - where the gods reside

Huginn (thought) reports the present state.
Muninn (memory) remembers all that was.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app, Counter, Histogram
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from structlog import get_logger, configure
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from src.core.config import get_settings
from src.models.registry import Base
from src.api.routes import router as api_router
from src.api.llm_config import router as llm_config_router
from src.norns.routes import router as norns_router
from src.services.deployment_manager import HealthCheckScheduler
from src.services.llm_model_watcher import LLMModelWatcher

# =============================================================================
# Configuration
# =============================================================================

settings = get_settings()

# Configure structured logging
configure(
    processors=[
        add_log_level,
        TimeStamper(fmt="iso"),
        JSONRenderer(),
    ],
)

logger = get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "ravenhelm_control_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "ravenhelm_control_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# =============================================================================
# Database Setup
# =============================================================================

engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("Starting Ravenhelm Control Plane", version=settings.APP_VERSION)
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created/verified")
    
    # Start health check scheduler
    scheduler = HealthCheckScheduler(async_session_factory)
    await scheduler.start()
    
    logger.info("Health check scheduler started")

    model_watcher = LLMModelWatcher(
        poll_interval_seconds=settings.LLM_PROVIDER_REFRESH_SECONDS,
        kafka_bootstrap=settings.KAFKA_BOOTSTRAP,
    )
    await model_watcher.start()
    logger.info("LLM model watcher started")
    
    yield
    
    # Shutdown
    await scheduler.stop()
    await model_watcher.stop()
    await engine.dispose()
    
    logger.info("Ravenhelm Control Plane shutdown complete")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="""
# Hliðskjálf — Odin's High Seat

*"From Hliðskjálf he could look out over all the worlds and see all things."*  
— Prose Edda

## The Nine Realms

| Realm | Purpose |
|-------|---------|
| **Midgard** | Development — the mortal realm where we build |
| **Alfheim** | Staging — the realm of light elves, pre-production |
| **Asgard** | Production — the realm of the gods, live and sacred |
| **Niflheim** | Disaster Recovery — the cold realm of mist |
| **Muspelheim** | Load Testing — the fire realm, chaos engineering |
| **Jotunheim** | Sandbox — the realm of giants, experiments |
| **Vanaheim** | Shared Services — the Vanir realm, platform infrastructure |
| **Svartalfheim** | Data — the dark elf realm, databases and analytics |
| **Helheim** | Archive — the realm of the dead, cold storage |

## The Ravens

**Huginn** (thought/perception) — Real-time state observation via NATS JetStream  
**Muninn** (memory) — Historical knowledge via Kafka/Redpanda and PostgreSQL

## Features

- **Bifröst Gateway**: Port registry with automatic allocation and conflict prevention
- **Yggdrasil Registry**: Track all projects across all realms
- **Realm Watch**: Monitor deployments from Midgard to Asgard
- **Raven Reports**: Health checks via Huginn, history via Muninn
- **Nginx Weaving**: Auto-generated routing from the registry

## Security — The Einherjar

All services bear SPIFFE IDs for zero-trust communication.  
Trust domain: `ravenhelm.local`  
Workload identity via SPIRE — only the worthy may enter Valhalla.
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# =============================================================================
# Middleware
# =============================================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://control.ravenhelm.test",
        "https://localhost:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect request metrics"""
    import time
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    endpoint = request.url.path
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(duration)
    
    return response


# =============================================================================
# OpenTelemetry Instrumentation
# =============================================================================

if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
    tracer_provider = TracerProvider()
    otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app)


# =============================================================================
# Routes
# =============================================================================

# Override the session dependency with actual implementation
from src.api import routes
routes.get_session = get_session

# API routes
app.include_router(api_router, prefix="/api/v1")

# LLM Configuration routes
app.include_router(llm_config_router, prefix="/api/v1")

# The Norns - AI Agent routes
app.include_router(norns_router, prefix="/api/v1")

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "service": "ravenhelm-control"}


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Readiness check - verifies database connection"""
    try:
        async with async_session_factory() as session:
            await session.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )

