from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DatabaseCredentials:
    username: str
    password: str
    host: str
    port: int
    database: str


# Primary (read-write) engine
engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None

# Read replica engine (optional)
read_engine: AsyncEngine | None = None
read_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


async def _fetch_credentials_from_secrets_manager() -> DatabaseCredentials:
    """Fetch database credentials from AWS Secrets Manager."""
    from app.core.aws_secrets import get_secret

    if not settings.DB_SECRET_NAME:
        raise ValueError("DB_SECRET_NAME not configured")

    logger.info("Fetching database credentials from Secrets Manager", secret=settings.DB_SECRET_NAME)

    secret = await get_secret(settings.DB_SECRET_NAME)

    # AWS RDS secrets have a standard format
    return DatabaseCredentials(
        username=secret.get("username", ""),
        password=secret.get("password", ""),
        host=secret.get("host", settings.DB_HOST),
        port=int(secret.get("port", settings.DB_PORT)),
        database=secret.get("dbname", settings.DB_NAME),
    )


def _build_database_url(creds: DatabaseCredentials, ssl_mode: str) -> str:
    """Build a PostgreSQL connection URL from credentials."""
    # URL-encode password to handle special characters
    encoded_password = quote_plus(creds.password)

    url = (
        f"postgresql+asyncpg://{creds.username}:{encoded_password}"
        f"@{creds.host}:{creds.port}/{creds.database}"
    )

    # asyncpg uses 'ssl' parameter, not 'sslmode'
    if ssl_mode in ("require", "verify-ca", "verify-full"):
        url += "?ssl=require"

    return url


def _get_ssl_connect_args() -> dict[str, Any]:
    """Get SSL connection arguments based on environment."""
    if settings.ENVIRONMENT == "production" or settings.DB_SSL_MODE in ("require", "verify-ca", "verify-full"):
        import ssl
        ssl_context = ssl.create_default_context()

        if settings.DB_SSL_MODE == "verify-full":
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        elif settings.DB_SSL_MODE == "verify-ca":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:
            # require - encrypt but don't verify
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        return {"ssl": ssl_context}

    return {}


def _create_engine(url: str, is_read_replica: bool = False) -> AsyncEngine:
    """Create a SQLAlchemy async engine with appropriate settings."""
    connect_args = _get_ssl_connect_args()

    # Read replicas can have larger pools since they handle more concurrent reads
    pool_size = settings.DB_POOL_SIZE * 2 if is_read_replica else settings.DB_POOL_SIZE

    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        connect_args=connect_args,
    )


async def init_db() -> None:
    """Initialize database connections.

    Connection strategy:
    - If DB_SECRET_NAME is set: fetch credentials from AWS Secrets Manager
    - Otherwise: use DATABASE_URL directly (for local development)

    For read replicas:
    - If DATABASE_READ_URL is set: create a separate read engine
    - Otherwise: reads go to the primary
    """
    global engine, async_session_factory, read_engine, read_session_factory

    # Determine the primary database URL
    if settings.DB_SECRET_NAME:
        # Production: fetch credentials from Secrets Manager
        creds = await _fetch_credentials_from_secrets_manager()
        primary_url = _build_database_url(creds, settings.DB_SSL_MODE)
        log_host = f"{creds.host}:{creds.port}/{creds.database}"
    else:
        # Development: use DATABASE_URL directly
        primary_url = settings.DATABASE_URL
        log_host = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured-url"

    logger.info("Initializing primary database connection", host=log_host, environment=settings.ENVIRONMENT)

    engine = _create_engine(primary_url, is_read_replica=False)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Initialize read replica if configured
    if settings.DATABASE_READ_URL:
        logger.info("Initializing read replica connection")
        read_engine = _create_engine(settings.DATABASE_READ_URL, is_read_replica=True)
        read_session_factory = async_sessionmaker(
            read_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    logger.info("Database connection initialized")


async def close_db() -> None:
    """Close all database connections."""
    global engine, read_engine

    if read_engine:
        logger.info("Closing read replica connection")
        await read_engine.dispose()
        read_engine = None

    if engine:
        logger.info("Closing primary database connection")
        await engine.dispose()
        engine = None


async def check_db_health() -> bool:
    """Check if the database is healthy."""
    if not engine:
        return False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


@asynccontextmanager
async def get_session(readonly: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    Args:
        readonly: If True and a read replica is configured, use the read replica.
                  Otherwise, use the primary database.
    """
    # Use read replica for readonly operations if available
    if readonly and read_session_factory:
        factory = read_session_factory
    elif async_session_factory:
        factory = async_session_factory
    else:
        raise RuntimeError("Database not initialized")

    session = factory()
    try:
        yield session
        if not readonly:
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions (read-write)."""
    async with get_session(readonly=False) as session:
        yield session


async def get_db_readonly() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for read-only database sessions.

    Uses the read replica if configured, otherwise falls back to primary.
    """
    async with get_session(readonly=True) as session:
        yield session


async def execute_raw(query: str, params: dict[str, Any] | None = None) -> Any:
    """Execute a raw SQL query."""
    async with get_session() as session:
        result = await session.execute(text(query), params or {})
        return result


async def set_tenant_context(session: AsyncSession, org_id: str) -> None:
    """Set the tenant context for Row-Level Security.

    This sets the app.current_org_id session variable that RLS policies use
    to filter data to the current tenant.

    Args:
        session: The database session
        org_id: The organization ID to set as the current tenant
    """
    await session.execute(
        text("SET LOCAL app.current_org_id = :org_id"),
        {"org_id": org_id},
    )


@asynccontextmanager
async def get_tenant_session(org_id: str, readonly: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with tenant context set.

    This is the preferred way to get a session when you need RLS-enforced
    tenant isolation.

    Args:
        org_id: The organization ID for tenant context
        readonly: If True and a read replica is configured, use the read replica
    """
    # Use read replica for readonly operations if available
    if readonly and read_session_factory:
        factory = read_session_factory
    elif async_session_factory:
        factory = async_session_factory
    else:
        raise RuntimeError("Database not initialized")

    session = factory()
    try:
        # Set tenant context for RLS
        await set_tenant_context(session, org_id)
        yield session
        if not readonly:
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_with_tenant(org_id: str) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency factory for tenant-scoped database sessions.

    Usage:
        @router.get("/items")
        async def list_items(
            tenant: RequireTenant,
            db: AsyncSession = Depends(lambda: get_db_with_tenant(tenant.org_id))
        ):
            ...

    For simpler usage, see TenantDbSession dependency in api/deps.py.
    """
    async with get_tenant_session(org_id, readonly=False) as session:
        yield session
