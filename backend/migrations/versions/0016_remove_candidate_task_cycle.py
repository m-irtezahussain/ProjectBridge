"""Remove the circular candidate-to-task foreign key.

Revision ID: 0016_remove_candidate_task_cycle
Revises: 0015_ingestion_pipeline
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_remove_candidate_task_cycle"
down_revision: str | None = "0015_ingestion_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "document_task_candidates_created_task_id_fkey",
        "document_task_candidates",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "document_task_candidates_created_task_id_fkey",
        "document_task_candidates",
        "tasks",
        ["created_task_id"],
        ["id"],
        ondelete="RESTRICT",
    )
