"""Security and observability middleware."""

from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Headers follow OWASP recommendations:
    https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable unnecessary browser features)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content Security Policy (API-appropriate)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # HSTS (only in production with HTTPS)
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Cache control for API responses
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use existing request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid4())

        # Store in request state for access in handlers
        request.state.request_id = request_id

        response = await call_next(request)

        # Echo request ID in response
        response.headers["X-Request-ID"] = request_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing and metadata.

    Also publishes audit events for compliance tracking.
    """

    # Paths to exclude from audit logging (high-volume, low-value)
    AUDIT_EXCLUDE_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import time

        start_time = time.perf_counter()

        # Get request ID if available
        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")

        # Log request start
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log request completion
        logger.info(
            "Request completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Publish audit event (async, non-blocking)
        if request.url.path not in self.AUDIT_EXCLUDE_PATHS:
            await self._publish_audit_event(
                request=request,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                client_ip=client_ip,
                user_agent=user_agent,
            )

        return response

    async def _publish_audit_event(
        self,
        request: Request,
        status_code: int,
        duration_ms: float,
        request_id: str,
        client_ip: str,
        user_agent: str,
    ) -> None:
        """Publish API call audit event."""
        try:
            from app.core.audit import audit_api_call, ActorType

            # Get actor info from request state (set by auth middleware)
            actor_id = "anonymous"
            actor_type = ActorType.USER
            org_id = None
            trace_id = None

            # Check if user is authenticated (set by auth dependencies)
            if hasattr(request.state, "user"):
                user = request.state.user
                actor_id = user.user_id
                org_id = user.org_id
                if user.token_type == "api_key":
                    actor_type = ActorType.SERVICE

            # Get trace ID from OpenTelemetry if available
            if hasattr(request.state, "trace_id"):
                trace_id = request.state.trace_id

            await audit_api_call(
                actor_id=actor_id,
                actor_type=actor_type,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                org_id=org_id,
                request_id=request_id,
                trace_id=trace_id,
                actor_ip=client_ip,
                user_agent=user_agent,
            )
        except Exception as e:
            # Audit logging should never break the request
            logger.warning("Failed to publish audit event", error=str(e))

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, considering proxy headers."""
        # Check X-Forwarded-For first (load balancer/proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


def setup_rate_limiter(app: ASGIApp) -> None:
    """Configure rate limiting for the application."""
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting disabled")
        return

    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
        storage_uri=settings.REDIS_URL,  # Use Redis for distributed rate limiting
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    logger.info(
        "Rate limiting enabled",
        default_limit=settings.RATE_LIMIT_DEFAULT,
        burst_limit=settings.RATE_LIMIT_BURST,
    )
