"""Authentication and authorization utilities.

Provides FastAPI dependencies for JWT validation, API key authentication,
and user/tenant context injection.

Supports both:
- Zitadel OIDC tokens (recommended)
- Legacy HS256 JWT tokens (deprecated)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decode_token, TokenPayload

logger = get_logger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class CurrentUser:
    """Represents the authenticated user context."""

    user_id: str
    email: str | None = None
    org_id: str | None = None
    roles: list[str] | None = None
    scopes: list[str] | None = None
    token_type: str = "access"  # access, refresh, api_key

    @property
    def is_service_account(self) -> bool:
        """Check if this is a service account (API key auth)."""
        return self.token_type == "api_key"


@dataclass
class TenantContext:
    """Represents the current tenant context for multi-tenancy."""

    org_id: str
    business_unit_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    environment: str = "development"


class AuthenticationError(HTTPException):
    """Authentication failed."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """Authorization failed - insufficient permissions."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def get_token_from_header(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    """Extract JWT token from Authorization header."""
    if credentials is None:
        return None
    return credentials.credentials


async def get_api_key_from_header(
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> str | None:
    """Extract API key from X-API-Key header."""
    return api_key


async def validate_jwt_token(token: str) -> CurrentUser:
    """Validate JWT token and return user context.

    Tries Zitadel OIDC validation first (RS256), falls back to legacy JWT (HS256).

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    # Try Zitadel OIDC validation first (RS256 tokens)
    try:
        from app.core.zitadel import validate_zitadel_token

        zitadel_payload = await validate_zitadel_token(token)
        logger.debug("Validated Zitadel OIDC token", user_id=zitadel_payload.sub)

        return CurrentUser(
            user_id=zitadel_payload.sub,
            email=zitadel_payload.email,
            org_id=zitadel_payload.org_id,
            roles=zitadel_payload.get_roles(),
            scopes=[],  # Zitadel uses roles, not OAuth scopes
            token_type="access",
        )
    except ValueError as e:
        logger.debug("Zitadel validation failed, trying legacy JWT", error=str(e))
    except Exception as e:
        # Network errors, etc. - try legacy fallback
        logger.warning("Zitadel validation error, trying legacy JWT", error=str(e))

    # Fall back to legacy HS256 JWT validation
    payload = decode_token(token, expected_type="access")
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    # Extract user info from token
    return CurrentUser(
        user_id=payload.sub,
        email=payload.model_dump().get("email"),
        org_id=payload.model_dump().get("org_id"),
        roles=payload.model_dump().get("roles", []),
        scopes=payload.model_dump().get("scopes", []),
        token_type="access",
    )


async def validate_api_key(api_key: str) -> CurrentUser:
    """Validate API key and return service account context.

    In production, this would look up the API key in a database
    or cache to get the associated service account.

    Raises:
        AuthenticationError: If API key is invalid.
    """
    # TODO: Implement API key lookup from database
    # For now, we validate format and return a placeholder
    if not api_key or len(api_key) < 32:
        raise AuthenticationError("Invalid API key")

    # In production: lookup API key in database
    # api_key_record = await db.get_api_key(hash_api_key(api_key))
    # if not api_key_record or api_key_record.revoked:
    #     raise AuthenticationError("Invalid or revoked API key")

    logger.warning("API key validation is using placeholder - implement database lookup")

    return CurrentUser(
        user_id=f"service:{api_key[:8]}",  # Placeholder
        org_id=None,  # Would come from API key record
        roles=["service"],
        scopes=["api:access"],
        token_type="api_key",
    )


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(get_token_from_header)],
    api_key: Annotated[str | None, Depends(get_api_key_from_header)],
) -> CurrentUser:
    """Get current authenticated user from JWT or API key.

    Tries JWT first, then API key.
    Stores user in request.state for audit logging middleware.

    Raises:
        AuthenticationError: If no valid credentials provided.
    """
    # Try JWT token first
    if token:
        try:
            user = await validate_jwt_token(token)
            request.state.auth_method = "jwt"
            request.state.user = user  # Store for audit middleware
            return user
        except AuthenticationError:
            # If JWT fails, try API key
            pass

    # Try API key
    if api_key:
        user = await validate_api_key(api_key)
        request.state.auth_method = "api_key"
        request.state.user = user  # Store for audit middleware
        return user

    # No valid credentials
    raise AuthenticationError("No valid credentials provided")


async def get_current_user_optional(
    request: Request,
    token: Annotated[str | None, Depends(get_token_from_header)],
    api_key: Annotated[str | None, Depends(get_api_key_from_header)],
) -> CurrentUser | None:
    """Get current user if authenticated, None otherwise.

    Use this for endpoints that work with or without authentication.
    User is stored in request.state for audit logging middleware.
    """
    try:
        user = await get_current_user(request, token, api_key)
        return user  # Already stored in request.state by get_current_user
    except AuthenticationError:
        return None


async def get_tenant_context(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantContext:
    """Get tenant context from authenticated user.

    Extracts org_id and other tenant identifiers from the user context
    or request headers.
    """
    # Get org_id from user token or header override (for admin users)
    org_id = user.org_id

    # Allow header override for admin/service accounts
    if user.is_service_account or "admin" in (user.roles or []):
        header_org_id = request.headers.get("X-Org-ID")
        if header_org_id:
            org_id = header_org_id

    if not org_id:
        raise AuthorizationError("Organization context required")

    return TenantContext(
        org_id=org_id,
        business_unit_id=request.headers.get("X-Business-Unit-ID"),
        team_id=request.headers.get("X-Team-ID"),
        project_id=request.headers.get("X-Project-ID"),
        environment=settings.ENVIRONMENT,
    )


def require_roles(*required_roles: str):
    """Dependency factory to require specific roles.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(user: CurrentUser = Depends(require_roles("admin"))):
            ...
    """

    async def role_checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        user_roles = set(user.roles or [])
        if not user_roles.intersection(required_roles):
            raise AuthorizationError(f"Required roles: {', '.join(required_roles)}")
        return user

    return role_checker


def require_scopes(*required_scopes: str):
    """Dependency factory to require specific scopes.

    Usage:
        @router.get("/data")
        async def data_endpoint(user: CurrentUser = Depends(require_scopes("read:data"))):
            ...
    """

    async def scope_checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        user_scopes = set(user.scopes or [])
        missing = set(required_scopes) - user_scopes
        if missing:
            raise AuthorizationError(f"Missing scopes: {', '.join(missing)}")
        return user

    return scope_checker


# Type aliases for common dependency patterns
RequireAuth = Annotated[CurrentUser, Depends(get_current_user)]
OptionalAuth = Annotated[CurrentUser | None, Depends(get_current_user_optional)]
RequireTenant = Annotated[TenantContext, Depends(get_tenant_context)]
