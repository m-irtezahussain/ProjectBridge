"""Add document, OCR, extraction, and action provenance.

Revision ID: 0017_provenance
Revises: 0016_remove_candidate_task_cycle
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_provenance"
down_revision: str | None = "0016_remove_candidate_task_cycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

action_origin = postgresql.ENUM(
    "rest", "mcp", "worker", name="action_origin", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    action_origin.create(bind, checkfirst=True)
    op.execute("ALTER TYPE task_source ADD VALUE IF NOT EXISTS 'rest'")
    op.execute("ALTER TYPE task_source ADD VALUE IF NOT EXISTS 'worker'")

    op.add_column(
        "documents",
        sa.Column(
            "created_via", action_origin, nullable=False, server_default="mcp"
        ),
    )
    op.add_column(
        "document_audit_events",
        sa.Column(
            "actor_origin", action_origin, nullable=False, server_default="mcp"
        ),
    )
    op.add_column(
        "document_ingestion_runs",
        sa.Column(
            "initiated_via", action_origin, nullable=False, server_default="mcp"
        ),
    )

    op.add_column(
        "document_texts", sa.Column("ingestion_run_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "document_texts",
        sa.Column("engine_version", sa.String(50), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "document_texts",
        sa.Column(
            "status",
            postgresql.ENUM(
                name="ingestion_stage_status", create_type=False
            ),
            nullable=False,
            server_default="completed",
        ),
    )
    op.add_column(
        "document_texts",
        sa.Column(
            "created_via", action_origin, nullable=False, server_default="worker"
        ),
    )
    op.execute(
        """
        UPDATE document_texts AS text
        SET ingestion_run_id = (
            SELECT run.id
            FROM document_ingestion_runs AS run
            WHERE run.document_id = text.document_id
            ORDER BY run.id ASC
            LIMIT 1
        )
        """
    )
    op.alter_column("document_texts", "ingestion_run_id", nullable=False)
    op.create_foreign_key(
        "fk_document_texts_ingestion_run",
        "document_texts",
        "document_ingestion_runs",
        ["ingestion_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_document_texts_ingestion_run_id",
        "document_texts",
        ["ingestion_run_id"],
    )
    op.drop_constraint("uq_document_text_document", "document_texts", type_="unique")
    op.create_unique_constraint(
        "uq_document_text_ingestion_run", "document_texts", ["ingestion_run_id"]
    )

    op.add_column(
        "document_task_candidates",
        sa.Column("source_text_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_task_candidates", sa.Column("source_line_start", sa.Integer())
    )
    op.add_column(
        "document_task_candidates", sa.Column("source_line_end", sa.Integer())
    )
    op.add_column(
        "document_task_candidates",
        sa.Column(
            "extractor",
            sa.String(100),
            nullable=False,
            server_default="safe_marker_extractor",
        ),
    )
    op.add_column(
        "document_task_candidates",
        sa.Column(
            "extractor_version", sa.String(50), nullable=False, server_default="1.0"
        ),
    )
    op.add_column(
        "document_task_candidates",
        sa.Column(
            "extracted_via", action_origin, nullable=False, server_default="worker"
        ),
    )
    op.execute(
        """
        UPDATE document_task_candidates AS candidate
        SET source_text_id = text.id
        FROM document_texts AS text
        WHERE text.document_id = candidate.document_id
        """
    )
    op.alter_column("document_task_candidates", "source_text_id", nullable=False)
    op.create_foreign_key(
        "fk_document_task_candidates_source_text",
        "document_task_candidates",
        "document_texts",
        ["source_text_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_document_task_candidates_source_text_id",
        "document_task_candidates",
        ["source_text_id"],
    )

    op.create_table(
        "document_ingestion_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer()),
        sa.Column("origin", action_origin, nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(50)),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"], ["document_ingestion_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    for column in ("ingestion_run_id", "business_id", "actor_user_id", "occurred_at"):
        op.create_index(
            f"ix_document_ingestion_events_{column}",
            "document_ingestion_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("document_ingestion_events")
    op.drop_index(
        "ix_document_task_candidates_source_text_id",
        table_name="document_task_candidates",
    )
    op.drop_constraint(
        "fk_document_task_candidates_source_text",
        "document_task_candidates",
        type_="foreignkey",
    )
    for column in (
        "extracted_via",
        "extractor_version",
        "extractor",
        "source_line_end",
        "source_line_start",
        "source_text_id",
    ):
        op.drop_column("document_task_candidates", column)
    op.drop_constraint(
        "uq_document_text_ingestion_run", "document_texts", type_="unique"
    )
    op.create_unique_constraint(
        "uq_document_text_document", "document_texts", ["document_id"]
    )
    op.drop_index("ix_document_texts_ingestion_run_id", table_name="document_texts")
    op.drop_constraint(
        "fk_document_texts_ingestion_run", "document_texts", type_="foreignkey"
    )
    for column in ("created_via", "status", "engine_version", "ingestion_run_id"):
        op.drop_column("document_texts", column)
    op.drop_column("document_ingestion_runs", "initiated_via")
    op.drop_column("document_audit_events", "actor_origin")
    op.drop_column("documents", "created_via")
    action_origin.drop(op.get_bind(), checkfirst=True)
