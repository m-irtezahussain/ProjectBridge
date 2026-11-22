"""Add MCP idempotency and audit records.

Revision ID: 0012_mcp_operations
Revises: 0011_mcp_oauth
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_mcp_operations"
down_revision: str | None = "0011_mcp_oauth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_idempotency_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "state", sa.String(length=20), server_default="started", nullable=False
        ),
        sa.Column("result_type", sa.String(length=50), nullable=True),
        sa.Column("result_id", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "grant_id",
            "tool_name",
            "key_hash",
            name="uq_mcp_idempotency_scope_key",
        ),
    )
    op.create_index(
        "ix_mcp_idempotency_records_business_id",
        "mcp_idempotency_records",
        ["business_id"],
    )
    op.create_table(
        "mcp_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mcp_audit_events_business_id", "mcp_audit_events", ["business_id"]
    )
    op.create_index(
        "ix_mcp_audit_events_user_id", "mcp_audit_events", ["user_id"]
    )
    op.create_index(
        "ix_mcp_audit_events_grant_id", "mcp_audit_events", ["grant_id"]
    )
    op.create_index(
        "ix_mcp_audit_events_occurred_at", "mcp_audit_events", ["occurred_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_audit_events_occurred_at", table_name="mcp_audit_events")
    op.drop_index("ix_mcp_audit_events_grant_id", table_name="mcp_audit_events")
    op.drop_index("ix_mcp_audit_events_user_id", table_name="mcp_audit_events")
    op.drop_index("ix_mcp_audit_events_business_id", table_name="mcp_audit_events")
    op.drop_table("mcp_audit_events")
    op.drop_index(
        "ix_mcp_idempotency_records_business_id",
        table_name="mcp_idempotency_records",
    )
    op.drop_table("mcp_idempotency_records")
