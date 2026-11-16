"""Create tenant-scoped project tasks.

Revision ID: 0010_create_tasks
Revises: 0009_project_description
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_create_tasks"
down_revision: str | None = "0009_project_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_status = postgresql.ENUM(
    "todo", "in process", "in review", "done", name="task_status", create_type=False
)
task_priority = postgresql.ENUM(
    "low", "medium", "high", "urgent", name="task_priority", create_type=False
)
task_source = postgresql.ENUM(
    "api", "mcp", name="task_source", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    task_status.create(bind, checkfirst=True)
    task_priority.create(bind, checkfirst=True)
    task_source.create(bind, checkfirst=True)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", task_status, server_default="todo", nullable=False),
        sa.Column("priority", task_priority, server_default="medium", nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by", task_source, server_default="api", nullable=False),
        sa.CheckConstraint("project_id > 0", name="ck_tasks_project_id_positive"),
        sa.CheckConstraint(
            "char_length(btrim(title)) BETWEEN 2 AND 200",
            name="ck_tasks_title_length",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_is_deleted", "tasks", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_tasks_is_deleted", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_table("tasks")
    task_source.drop(op.get_bind(), checkfirst=True)
    task_priority.drop(op.get_bind(), checkfirst=True)
    task_status.drop(op.get_bind(), checkfirst=True)
