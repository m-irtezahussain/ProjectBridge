"""Strengthen mutation idempotency, versions, and ingestion deduplication.

Revision ID: 0020_mutation_guarantees
Revises: 0019_resource_indexes
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_mutation_guarantees"
down_revision: str | None = "0019_resource_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_idempotency_records",
        sa.Column(
            "recovery_point",
            sa.String(50),
            nullable=False,
            server_default="started",
        ),
    )
    op.add_column(
        "mcp_idempotency_records",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "mcp_idempotency_records",
        sa.Column("locked_until", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "mcp_idempotency_records",
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "mcp_idempotency_records",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        """
        UPDATE mcp_idempotency_records
        SET expires_at = created_at + interval '7 days',
            locked_until = CASE
                WHEN state = 'started' THEN created_at + interval '60 seconds'
                ELSE NULL
            END,
            recovery_point = CASE
                WHEN state = 'completed' THEN 'completed'
                ELSE 'started'
            END
        """
    )
    op.alter_column("mcp_idempotency_records", "expires_at", nullable=False)
    op.create_index(
        "ix_mcp_idempotency_records_expires_at",
        "mcp_idempotency_records",
        ["expires_at"],
    )
    op.create_index(
        "ix_mcp_idempotency_records_state_locked_until",
        "mcp_idempotency_records",
        ["state", "locked_until"],
    )

    for table in ("projects", "tasks", "documents", "document_ingestion_runs"):
        op.add_column(
            table,
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_check_constraint(
            f"ck_{table}_version_positive", table, "version > 0"
        )

    op.add_column(
        "document_task_candidates",
        sa.Column("dedupe_key", sa.String(64)),
    )
    op.execute(
        """
        WITH candidate_keys AS (
            SELECT id,
                   encode(sha256(convert_to(
                       coalesce(source_line_start::text, '0') || E'\\n' ||
                       title || E'\\n' || source_excerpt,
                       'UTF8'
                   )), 'hex') AS base_key,
                   row_number() OVER (
                       PARTITION BY ingestion_run_id,
                           coalesce(source_line_start::text, '0'),
                           title,
                           source_excerpt
                       ORDER BY id
                   ) AS duplicate_number
            FROM document_task_candidates
        )
        UPDATE document_task_candidates AS candidate
        SET dedupe_key = CASE
            WHEN candidate_keys.duplicate_number = 1 THEN candidate_keys.base_key
            ELSE encode(sha256(convert_to(
                candidate_keys.base_key || E'\\nlegacy-duplicate:' || candidate.id,
                'UTF8'
            )), 'hex')
        END
        FROM candidate_keys
        WHERE candidate.id = candidate_keys.id
        """
    )
    op.alter_column("document_task_candidates", "dedupe_key", nullable=False)
    op.create_unique_constraint(
        "uq_task_candidate_run_dedupe_key",
        "document_task_candidates",
        ["ingestion_run_id", "dedupe_key"],
    )
    op.execute(
        """
        WITH active_runs AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY document_id
                       ORDER BY id DESC
                   ) AS active_number
            FROM document_ingestion_runs
            WHERE status NOT IN ('completed', 'failed')
        )
        UPDATE document_ingestion_runs AS run
        SET status = 'failed',
            last_error_stage = 'migration',
            last_error_code = 'duplicate_active_ingestion',
            last_error_message =
                'Superseded while enforcing one active ingestion per document'
        FROM active_runs
        WHERE run.id = active_runs.id
          AND active_runs.active_number > 1
        """
    )
    op.create_index(
        "uq_document_ingestion_active_document",
        "document_ingestion_runs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('completed', 'failed')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_document_ingestion_active_document",
        table_name="document_ingestion_runs",
    )
    op.drop_constraint(
        "uq_task_candidate_run_dedupe_key",
        "document_task_candidates",
        type_="unique",
    )
    op.drop_column("document_task_candidates", "dedupe_key")
    for table in ("document_ingestion_runs", "documents", "tasks", "projects"):
        op.drop_constraint(f"ck_{table}_version_positive", table, type_="check")
        op.drop_column(table, "version")
    op.drop_index(
        "ix_mcp_idempotency_records_state_locked_until",
        table_name="mcp_idempotency_records",
    )
    op.drop_index(
        "ix_mcp_idempotency_records_expires_at",
        table_name="mcp_idempotency_records",
    )
    op.drop_column("mcp_idempotency_records", "updated_at")
    op.drop_column("mcp_idempotency_records", "expires_at")
    op.drop_column("mcp_idempotency_records", "locked_until")
    op.drop_column("mcp_idempotency_records", "attempt_count")
    op.drop_column("mcp_idempotency_records", "recovery_point")
