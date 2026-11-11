"""Initialize the ProjectBridge schema baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-11
"""

from collections.abc import Sequence

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish a migration baseline; domain tables arrive with their features."""


def downgrade() -> None:
    """Remove the empty migration baseline."""

