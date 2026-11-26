"""Add indexes for MCP resource keyset pagination.

Revision ID: 0019_resource_indexes
Revises: 0018_rag_index_jobs
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_resource_indexes"
down_revision: str | None = "0018_rag_index_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_projects_business_active_id_desc",
        "projects",
        ["business_id", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_tasks_project_active_id_desc",
        "tasks",
        ["project_id", "id"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_documents_business_active_id_desc",
        "documents",
        ["business_id", "id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_documents_business_project_active_id_desc",
        "documents",
        ["business_id", "project_id", "id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_documents_business_project_active_id_desc", table_name="documents"
    )
    op.drop_index("ix_documents_business_active_id_desc", table_name="documents")
    op.drop_index("ix_tasks_project_active_id_desc", table_name="tasks")
    op.drop_index("ix_projects_business_active_id_desc", table_name="projects")
