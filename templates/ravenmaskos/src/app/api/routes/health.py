from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.core.db import check_db_health
from app.core.cache import check_redis_health
from app.core.kafka import check_kafka_health
from app.core.logging import get_logger
from app.core.config import settings
from app.api.deps import OptionalAuth, CurrentUser

router = APIRouter()
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, str]
    version: str = "0.1.0"
    environment: str = "unknown"


class DetailedHealthResponse(HealthResponse):
    authenticated: bool = False
    user_id: str | None = None


@router.get("/health", response_model=DetailedHealthResponse)
async def health_check(
    request: Request,
    user: OptionalAuth,
) -> DetailedHealthResponse:
    """Basic health check endpoint.

    Returns service status. If authenticated, includes user context.
    This endpoint is public but shows additional info when authenticated.
    """
    return DetailedHealthResponse(
        status="ok",
        checks={},
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        authenticated=user is not None,
        user_id=user.user_id if user else None,
    )


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(response: Response) -> HealthResponse:
    """Readiness probe for Kubernetes.

    Checks all external dependencies (database, cache, message queue).
    Returns 503 if any dependency is unhealthy.
    """
    checks: dict[str, str] = {}
    all_healthy = True

    db_healthy = await check_db_health()
    checks["database"] = "ok" if db_healthy else "error"
    if not db_healthy:
        all_healthy = False

    redis_healthy = await check_redis_health()
    checks["redis"] = "ok" if redis_healthy else "error"
    if not redis_healthy:
        all_healthy = False

    kafka_healthy = await check_kafka_health()
    checks["kafka"] = "ok" if kafka_healthy else "error"
    if not kafka_healthy:
        all_healthy = False

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("Readiness check failed", checks=checks)

    return HealthResponse(
        status="ok" if all_healthy else "degraded",
        checks=checks,
        version="0.1.0",
        environment=settings.ENVIRONMENT,
    )
