"""Initial tenant models with Row-Level Security.

Revision ID: 001_initial
Revises:
Create Date: 2024-11-29 00:00:00.000000+00:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial tenant tables with RLS."""
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("tier", sa.String(50), default="free", nullable=False),
        sa.Column("settings", postgresql.JSONB(), default=dict, nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_is_active", "organizations", ["is_active"])
    op.create_index("ix_organizations_tier", "organizations", ["tier"])

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column(
            "roles", postgresql.ARRAY(sa.String(50)), default=list, nullable=False
        ),
        sa.Column(
            "scopes", postgresql.ARRAY(sa.String(100)), default=list, nullable=False
        ),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("identity_provider", sa.String(50), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), default=0, nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), default=False, nullable=False),
        sa.Column("mfa_secret", sa.String(255), nullable=True),
        sa.Column(
            "preferences", postgresql.JSONB(), default=dict, nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_org_is_active", "users", ["org_id", "is_active"])
    op.create_unique_constraint("uq_users_org_email", "users", ["org_id", "email"])
    op.create_unique_constraint(
        "uq_users_org_provider_external_id",
        "users",
        ["org_id", "identity_provider", "external_id"],
    )

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scopes", postgresql.ARRAY(sa.String(100)), default=list, nullable=False
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), default=0, nullable=False),
        sa.Column("allowed_ips", postgresql.ARRAY(sa.String(45)), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    op.create_index("ix_api_keys_key_prefix_active", "api_keys", ["key_prefix", "is_active"])
    op.create_index("ix_api_keys_org_is_active", "api_keys", ["org_id", "is_active"])

    # Enable Row-Level Security on tenant tables
    # Note: RLS policies use app.current_org_id session variable
    op.execute("""
        -- Enable RLS on users table
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        ALTER TABLE users FORCE ROW LEVEL SECURITY;

        -- Create tenant isolation policy for users
        CREATE POLICY users_tenant_isolation ON users
            FOR ALL
            USING (org_id::text = current_setting('app.current_org_id', true))
            WITH CHECK (org_id::text = current_setting('app.current_org_id', true));

        -- Enable RLS on api_keys table
        ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
        ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;

        -- Create tenant isolation policy for api_keys
        CREATE POLICY api_keys_tenant_isolation ON api_keys
            FOR ALL
            USING (org_id::text = current_setting('app.current_org_id', true))
            WITH CHECK (org_id::text = current_setting('app.current_org_id', true));
    """)

    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Add updated_at triggers
    for table in ["organizations", "users", "api_keys"]:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    """Drop tenant tables and RLS policies."""
    # Drop triggers
    for table in ["organizations", "users", "api_keys"]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS users_tenant_isolation ON users;")
    op.execute("DROP POLICY IF EXISTS api_keys_tenant_isolation ON api_keys;")

    # Disable RLS
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY;")

    # Drop tables
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")
