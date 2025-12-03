"""Multi-tenant models for organization and user management.

These models form the foundation of the multi-tenant architecture:
- Organization: Top-level tenant entity
- User: Users belonging to organizations
- ApiKey: Service account API keys for programmatic access
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Organization (tenant) entity.

    The top-level entity for multi-tenancy. All tenant-scoped data
    references an organization through org_id.
    """

    __tablename__ = "organizations"

    # Organization details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Subscription/billing tier
    tier: Mapped[str] = mapped_column(
        String(50), default="free", nullable=False
    )  # free, starter, professional, enterprise

    # Settings stored as JSON
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Metadata
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
    api_keys: Mapped[list["ApiKey"]] = relationship("ApiKey", back_populates="organization")

    __table_args__ = (
        Index("ix_organizations_is_active", "is_active"),
        Index("ix_organizations_tier", "tier"),
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """User entity belonging to an organization.

    Users are scoped to a single organization. For users that need
    access to multiple organizations, create separate user records.
    """

    __tablename__ = "users"

    # Organization reference (tenant isolation)
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # User identity
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Authentication
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Profile
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Authorization
    roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, nullable=False
    )  # admin, member, viewer, etc.
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, nullable=False
    )  # Fine-grained permissions

    # External identity (for SSO)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identity_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # google, okta, azure-ad, etc.

    # Security
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Preferences stored as JSON
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")

    __table_args__ = (
        # Email unique within organization
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        # External ID unique within org and provider
        UniqueConstraint(
            "org_id", "identity_provider", "external_id", name="uq_users_org_provider_external_id"
        ),
        Index("ix_users_org_is_active", "org_id", "is_active"),
        Index("ix_users_email", "email"),
        # RLS will be enabled on this table
        {"info": {"rls_enabled": True}},
    )

    @property
    def is_locked(self) -> bool:
        """Check if the user account is locked."""
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until


class ApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """API Key for programmatic/service account access.

    API keys are scoped to an organization and can have
    restricted permissions via scopes.
    """

    __tablename__ = "api_keys"

    # Organization reference (tenant isolation)
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Key identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The actual key (hashed, prefix stored separately for identification)
    key_prefix: Mapped[str] = mapped_column(
        String(8), nullable=False, index=True
    )  # First 8 chars for lookup
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # Argon2id hash

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Permissions
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, nullable=False
    )  # Allowed API scopes

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # IP restrictions (optional)
    allowed_ips: Mapped[list[str] | None] = mapped_column(ARRAY(String(45)), nullable=True)

    # Metadata
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )  # User ID who created

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_org_is_active", "org_id", "is_active"),
        Index("ix_api_keys_key_prefix_active", "key_prefix", "is_active"),
        # RLS will be enabled on this table
        {"info": {"rls_enabled": True}},
    )

    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if the API key has been revoked."""
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid (active, not expired, not revoked)."""
        return self.is_active and not self.is_expired and not self.is_revoked
