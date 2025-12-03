"""FastAPI dependencies for API routes.

This module re-exports commonly used dependencies for cleaner imports in routes.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    CurrentUser,
    TenantContext,
    get_current_user,
    get_current_user_optional,
    get_tenant_context,
    require_roles,
    require_scopes,
    RequireAuth,
    OptionalAuth,
    RequireTenant,
)
from app.core.db import get_db, get_db_readonly, set_tenant_context

# Re-export auth dependencies
__all__ = [
    # Types
    "CurrentUser",
    "TenantContext",
    # Dependencies
    "get_current_user",
    "get_current_user_optional",
    "get_tenant_context",
    "require_roles",
    "require_scopes",
    # Type aliases
    "RequireAuth",
    "OptionalAuth",
    "RequireTenant",
    # Database
    "DbSession",
    "DbSessionReadonly",
    "TenantDbSession",
    # Request
    "RequestID",
]

# Database session dependencies
DbSession = Annotated[AsyncSession, Depends(get_db)]
DbSessionReadonly = Annotated[AsyncSession, Depends(get_db_readonly)]


async def get_tenant_db(
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncSession:
    """Get a database session with tenant context set for RLS.

    This dependency automatically sets the tenant context based on
    the authenticated user's organization, enabling Row-Level Security.

    Usage:
        @router.get("/items")
        async def list_items(db: TenantDbSession):
            # All queries will be automatically filtered by org_id
            return await db.execute(select(Item))
    """
    from app.core.db import async_session_factory

    if not async_session_factory:
        raise RuntimeError("Database not initialized")

    session = async_session_factory()
    try:
        await set_tenant_context(session, tenant.org_id)
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


TenantDbSession = Annotated[AsyncSession, Depends(get_tenant_db)]


async def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")


RequestID = Annotated[str, Depends(get_request_id)]
