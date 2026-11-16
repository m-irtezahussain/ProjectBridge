"""Create tenant-scoped projects with soft dismissal.

Revision ID: 0008_create_projects
Revises: 0007_refresh_retry_grace
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_create_projects"
down_revision: str | None = "0007_refresh_retry_grace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

project_status = postgresql.ENUM(
    "Active",
    "Planning",
    "At risk",
    "Completed",
    name="project_status",
    create_type=False,
)


def upgrade() -> None:
    project_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            project_status,
            server_default="Planning",
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "business_id > 0", name="ck_projects_business_id_positive"
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 2 AND 200",
            name="ck_projects_name_length",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["business.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_business_id", "projects", ["business_id"])
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_projects_deleted_at", table_name="projects")
    op.drop_index("ix_projects_business_id", table_name="projects")
    op.drop_table("projects")
    project_status.drop(op.get_bind(), checkfirst=True)
