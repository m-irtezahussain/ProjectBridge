"""Add an optional project description.

Revision ID: 0009_project_description
Revises: 0008_create_projects
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_project_description"
down_revision: str | None = "0008_create_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("description", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "description")
