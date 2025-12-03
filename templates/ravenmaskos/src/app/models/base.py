"""Base model mixins for SQLAlchemy models.

Provides common functionality like timestamps, soft deletes, and tenant isolation.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, event, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.db import Base


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that adds soft delete functionality."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        self.deleted_at = None


class TenantMixin:
    """Mixin that adds organization-level multi-tenancy.

    Uses PostgreSQL Row-Level Security (RLS) for tenant isolation.
    The org_id column is used for RLS policies.
    """

    org_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    @declared_attr
    def __table_args__(cls) -> tuple[Any, ...]:
        """Add RLS policy hint in table args."""
        return (
            # Index for efficient tenant queries
            # The actual RLS policy is created in migrations
            {"info": {"rls_enabled": True}},
        )


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )


# SQL for enabling RLS on a table (used in migrations)
RLS_ENABLE_SQL = """
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;
"""

RLS_POLICY_SQL = """
CREATE POLICY {policy_name} ON {table_name}
    FOR ALL
    USING (org_id = current_setting('app.current_org_id', true))
    WITH CHECK (org_id = current_setting('app.current_org_id', true));
"""

RLS_DROP_POLICY_SQL = """
DROP POLICY IF EXISTS {policy_name} ON {table_name};
"""

RLS_DISABLE_SQL = """
ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;
"""


def create_rls_policy(table_name: str, policy_name: str | None = None) -> str:
    """Generate SQL to create RLS policy for a tenant table.

    Args:
        table_name: Name of the table
        policy_name: Optional custom policy name (defaults to {table}_tenant_isolation)

    Returns:
        SQL string to execute
    """
    policy = policy_name or f"{table_name}_tenant_isolation"
    return RLS_ENABLE_SQL.format(table_name=table_name) + RLS_POLICY_SQL.format(
        table_name=table_name, policy_name=policy
    )


def drop_rls_policy(table_name: str, policy_name: str | None = None) -> str:
    """Generate SQL to drop RLS policy from a table.

    Args:
        table_name: Name of the table
        policy_name: Optional custom policy name (defaults to {table}_tenant_isolation)

    Returns:
        SQL string to execute
    """
    policy = policy_name or f"{table_name}_tenant_isolation"
    return RLS_DROP_POLICY_SQL.format(
        table_name=table_name, policy_name=policy
    ) + RLS_DISABLE_SQL.format(table_name=table_name)
