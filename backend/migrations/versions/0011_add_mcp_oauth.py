"""Add OAuth grants and credentials for MCP clients.

Revision ID: 0011_mcp_oauth
Revises: 0010_create_tasks
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_mcp_oauth"
down_revision: str | None = "0010_create_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("client_id"),
    )
    op.create_table(
        "oauth_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("resource", sa.String(length=1024), nullable=False),
        sa.Column("scopes", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_clients.client_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_grants_client_id", "oauth_grants", ["client_id"])
    op.create_index("ix_oauth_grants_user_id", "oauth_grants", ["user_id"])
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["grant_id"], ["oauth_grants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_oauth_authorization_codes_code_hash"),
    )
    op.create_index(
        "ix_oauth_authorization_codes_grant_id",
        "oauth_authorization_codes",
        ["grant_id"],
    )
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_by_token_hash", sa.String(length=64), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["grant_id"], ["oauth_grants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_oauth_refresh_tokens_token_hash"),
    )
    op.create_index(
        "ix_oauth_refresh_tokens_family_id", "oauth_refresh_tokens", ["family_id"]
    )
    op.create_index(
        "ix_oauth_refresh_tokens_grant_id", "oauth_refresh_tokens", ["grant_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_refresh_tokens_grant_id", table_name="oauth_refresh_tokens")
    op.drop_index("ix_oauth_refresh_tokens_family_id", table_name="oauth_refresh_tokens")
    op.drop_table("oauth_refresh_tokens")
    op.drop_index(
        "ix_oauth_authorization_codes_grant_id",
        table_name="oauth_authorization_codes",
    )
    op.drop_table("oauth_authorization_codes")
    op.drop_index("ix_oauth_grants_user_id", table_name="oauth_grants")
    op.drop_index("ix_oauth_grants_client_id", table_name="oauth_grants")
    op.drop_table("oauth_grants")
    op.drop_table("oauth_clients")
