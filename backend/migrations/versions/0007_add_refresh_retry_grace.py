"""Track the replacement token for idempotent refresh retries.

Revision ID: 0007_refresh_retry_grace
Revises: 0006_refresh_tokens
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_refresh_retry_grace"
down_revision: str | None = "0006_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("replaced_by_token_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "replaced_by_token_hash")
