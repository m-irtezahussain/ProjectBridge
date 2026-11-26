"""Add durable RAG synchronization jobs and chunk provenance.

Revision ID: 0018_rag_index_jobs
Revises: 0017_provenance
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_rag_index_jobs"
down_revision: str | None = "0017_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

job_operation = postgresql.ENUM(
    "upsert_document",
    "delete_document",
    "upsert_task",
    "delete_task",
    "delete_project",
    "reindex_project",
    name="search_job_operation",
    create_type=False,
)
job_status = postgresql.ENUM(
    "queued",
    "processing",
    "retry_scheduled",
    "completed",
    "failed",
    name="search_job_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    job_operation.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)

    op.add_column(
        "document_search_chunks",
        sa.Column("source_text_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_search_chunks",
        sa.Column("ingestion_run_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE document_search_chunks AS chunk
        SET source_text_id = (
            SELECT text.id
            FROM document_texts AS text
            WHERE text.document_id = chunk.document_id
            ORDER BY text.updated_at DESC, text.id DESC
            LIMIT 1
        ),
        ingestion_run_id = (
            SELECT text.ingestion_run_id
            FROM document_texts AS text
            WHERE text.document_id = chunk.document_id
            ORDER BY text.updated_at DESC, text.id DESC
            LIMIT 1
        )
        """
    )
    op.alter_column("document_search_chunks", "source_text_id", nullable=False)
    op.alter_column("document_search_chunks", "ingestion_run_id", nullable=False)
    op.create_foreign_key(
        "fk_document_search_chunks_source_text",
        "document_search_chunks",
        "document_texts",
        ["source_text_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_document_search_chunks_ingestion_run",
        "document_search_chunks",
        "document_ingestion_runs",
        ["ingestion_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_document_search_chunks_source_text_id",
        "document_search_chunks",
        ["source_text_id"],
    )
    op.create_index(
        "ix_document_search_chunks_ingestion_run_id",
        "document_search_chunks",
        ["ingestion_run_id"],
    )

    op.create_table(
        "search_index_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer()),
        sa.Column("document_id", sa.Integer()),
        sa.Column("task_id", sa.Integer()),
        sa.Column("operation", job_operation, nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
    )
    for column in (
        "business_id",
        "project_id",
        "document_id",
        "task_id",
        "operation",
        "status",
        "next_attempt_at",
        "locked_at",
    ):
        op.create_index(f"ix_search_index_jobs_{column}", "search_index_jobs", [column])


def downgrade() -> None:
    op.drop_table("search_index_jobs")
    op.drop_index(
        "ix_document_search_chunks_ingestion_run_id",
        table_name="document_search_chunks",
    )
    op.drop_index(
        "ix_document_search_chunks_source_text_id",
        table_name="document_search_chunks",
    )
    op.drop_constraint(
        "fk_document_search_chunks_ingestion_run",
        "document_search_chunks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_document_search_chunks_source_text",
        "document_search_chunks",
        type_="foreignkey",
    )
    op.drop_column("document_search_chunks", "ingestion_run_id")
    op.drop_column("document_search_chunks", "source_text_id")
    job_status.drop(op.get_bind(), checkfirst=True)
    job_operation.drop(op.get_bind(), checkfirst=True)
