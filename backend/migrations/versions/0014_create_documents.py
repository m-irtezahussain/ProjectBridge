"""Create tenant-scoped immutable document metadata and audit history.

Revision ID: 0014_create_documents
Revises: 0013_task_assignee
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_create_documents"
down_revision: str | None = "0013_task_assignee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_status = postgresql.ENUM(
    "pending",
    "validating",
    "available",
    "duplicate",
    "failed",
    "archived",
    name="document_status",
    create_type=False,
)


def upgrade() -> None:
    document_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=200), nullable=False),
        sa.Column("declared_mime_type", sa.String(length=100), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=True),
        sa.Column("declared_size", sa.BigInteger(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("quarantine_key", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column(
            "status", document_status, server_default="pending", nullable=False
        ),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("duplicate_of_document_id", sa.Integer(), nullable=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "declared_size > 0", name="ck_documents_declared_size_positive"
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0",
            name="ck_documents_size_bytes_positive",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["business.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_document_id"], ["documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quarantine_key"),
    )
    op.create_index("ix_documents_business_id", "documents", ["business_id"])
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index(
        "ix_documents_uploaded_by_user_id", "documents", ["uploaded_by_user_id"]
    )
    op.create_index("ix_documents_content_sha256", "documents", ["content_sha256"])
    op.create_index("ix_documents_storage_key", "documents", ["storage_key"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index(
        "ix_documents_duplicate_of_document_id",
        "documents",
        ["duplicate_of_document_id"],
    )
    op.create_table(
        "document_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["business.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_audit_events_document_id",
        "document_audit_events",
        ["document_id"],
    )
    op.create_index(
        "ix_document_audit_events_business_id",
        "document_audit_events",
        ["business_id"],
    )
    op.create_index(
        "ix_document_audit_events_actor_user_id",
        "document_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_document_audit_events_occurred_at",
        "document_audit_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_audit_events_occurred_at",
        table_name="document_audit_events",
    )
    op.drop_index(
        "ix_document_audit_events_actor_user_id",
        table_name="document_audit_events",
    )
    op.drop_index(
        "ix_document_audit_events_business_id",
        table_name="document_audit_events",
    )
    op.drop_index(
        "ix_document_audit_events_document_id",
        table_name="document_audit_events",
    )
    op.drop_table("document_audit_events")
    op.drop_index("ix_documents_duplicate_of_document_id", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_storage_key", table_name="documents")
    op.drop_index("ix_documents_content_sha256", table_name="documents")
    op.drop_index("ix_documents_uploaded_by_user_id", table_name="documents")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_index("ix_documents_business_id", table_name="documents")
    op.drop_table("documents")
    document_status.drop(op.get_bind(), checkfirst=True)
