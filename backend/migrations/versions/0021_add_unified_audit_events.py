"""Add the unified append-only audit event stream.

Revision ID: 0021_unified_audit
Revises: 0020_mutation_guarantees
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_unified_audit"
down_revision: str | None = "0020_mutation_guarantees"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer()),
        sa.Column(
            "interface",
            postgresql.ENUM(
                "rest",
                "mcp",
                "worker",
                name="action_origin",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.Integer()),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["business.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_business_id_id",
        "audit_events",
        ["business_id", "id"],
    )
    op.create_index(
        "ix_audit_events_business_action_id",
        "audit_events",
        ["business_id", "action", "id"],
    )
    op.create_index(
        "ix_audit_events_business_target_id",
        "audit_events",
        ["business_id", "target_type", "target_id", "id"],
    )

    op.execute(
        """
        INSERT INTO audit_events (
            business_id, actor_user_id, interface, action, target_type,
            target_id, outcome, occurred_at
        )
        SELECT business_id, user_id, 'mcp'::action_origin, tool_name,
               target_type, target_id, outcome, occurred_at
        FROM mcp_audit_events
        """
    )
    op.execute(
        """
        INSERT INTO audit_events (
            business_id, actor_user_id, interface, action, target_type,
            target_id, outcome, details, occurred_at
        )
        SELECT business_id, actor_user_id, actor_origin,
               'document.' || action, 'document', document_id,
               outcome, details, occurred_at
        FROM document_audit_events
        """
    )
    op.execute(
        """
        INSERT INTO audit_events (
            business_id, actor_user_id, interface, action, target_type,
            target_id, outcome, details, occurred_at
        )
        SELECT business_id, actor_user_id, origin,
               'ingestion.' || action, 'ingestion_run', ingestion_run_id,
               outcome,
               coalesce(details::jsonb, '{}'::jsonb) ||
                   jsonb_build_object('stage', stage, 'worker_id', worker_id),
               occurred_at
        FROM document_ingestion_events
        """
    )

    op.execute(
        """
        CREATE FUNCTION reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION reject_audit_event_mutation()")
    op.drop_index("ix_audit_events_business_target_id", table_name="audit_events")
    op.drop_index("ix_audit_events_business_action_id", table_name="audit_events")
    op.drop_index("ix_audit_events_business_id_id", table_name="audit_events")
    op.drop_table("audit_events")
