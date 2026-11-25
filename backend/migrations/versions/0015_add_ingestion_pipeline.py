"""Add durable OCR ingestion pipeline and source-linked tasks.

Revision ID: 0015_ingestion_pipeline
Revises: 0014_create_documents
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_ingestion_pipeline"
down_revision: str | None = "0014_create_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ingestion_status = postgresql.ENUM(
    "queued",
    "processing",
    "awaiting_confirmation",
    "retry_scheduled",
    "completed",
    "partial_failure",
    "failed",
    name="ingestion_status",
    create_type=False,
)
stage_status = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    name="ingestion_stage_status",
    create_type=False,
)
candidate_status = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    "created",
    "failed",
    name="task_candidate_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    ingestion_status.create(bind, checkfirst=True)
    stage_status.create(bind, checkfirst=True)
    candidate_status.create(bind, checkfirst=True)
    op.create_table(
        "document_texts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("engine", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("average_confidence", sa.Float()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("document_id", name="uq_document_text_document"),
    )
    op.create_index("ix_document_texts_document_id", "document_texts", ["document_id"])
    op.create_index("ix_document_texts_business_id", "document_texts", ["business_id"])
    op.create_table(
        "document_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("grant_id", sa.String(36), nullable=False),
        sa.Column("status", ingestion_status, server_default="queued", nullable=False),
        sa.Column("ocr_status", stage_status, server_default="pending", nullable=False),
        sa.Column("extraction_status", stage_status, server_default="pending", nullable=False),
        sa.Column("task_status", stage_status, server_default="pending", nullable=False),
        sa.Column("indexing_status", stage_status, server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("last_error_stage", sa.String(50)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("last_error_message", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    for column in ("document_id", "business_id", "project_id", "status", "locked_at"):
        op.create_index(f"ix_document_ingestion_runs_{column}", "document_ingestion_runs", [column])
    op.create_table(
        "document_task_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("source_excerpt", sa.String(500), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", candidate_status, server_default="pending", nullable=False),
        sa.Column("created_task_id", sa.Integer()),
        sa.Column("failure_message", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"], ["document_ingestion_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_task_id"], ["tasks.id"], ondelete="RESTRICT"),
    )
    for column in ("ingestion_run_id", "document_id", "business_id", "status"):
        op.create_index(
            f"ix_document_task_candidates_{column}", "document_task_candidates", [column]
        )
    op.add_column("tasks", sa.Column("source_document_id", sa.Integer()))
    op.add_column("tasks", sa.Column("source_candidate_id", sa.Integer()))
    op.create_foreign_key(
        "fk_tasks_source_document",
        "tasks",
        "documents",
        ["source_document_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_tasks_source_candidate",
        "tasks",
        "document_task_candidates",
        ["source_candidate_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_tasks_source_document_id", "tasks", ["source_document_id"])
    op.create_unique_constraint("uq_tasks_source_candidate_id", "tasks", ["source_candidate_id"])
    op.create_table(
        "document_search_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_search_chunk_index"),
    )
    for column in ("business_id", "project_id", "document_id"):
        op.create_index(f"ix_document_search_chunks_{column}", "document_search_chunks", [column])
    op.create_index(
        "ix_document_search_chunks_vector",
        "document_search_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("document_search_chunks")
    op.drop_constraint("uq_tasks_source_candidate_id", "tasks", type_="unique")
    op.drop_index("ix_tasks_source_document_id", table_name="tasks")
    op.drop_constraint("fk_tasks_source_candidate", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_source_document", "tasks", type_="foreignkey")
    op.drop_column("tasks", "source_candidate_id")
    op.drop_column("tasks", "source_document_id")
    op.drop_table("document_task_candidates")
    op.drop_table("document_ingestion_runs")
    op.drop_table("document_texts")
    candidate_status.drop(op.get_bind(), checkfirst=True)
    stage_status.drop(op.get_bind(), checkfirst=True)
    ingestion_status.drop(op.get_bind(), checkfirst=True)
