"""Allow each onboarding user to own exactly one business at most.

Revision ID: 0004_one_business_owner
Revises: 0003_validation_constraints
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_one_business_owner"
down_revision: str | None = "0003_validation_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_business_owned_by", "business", ["owned_by"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_business_owned_by", "business", type_="unique")
