"""Prevent actor deletion from mutating append-only audit events.

Revision ID: 0022_audit_actor_restrict
Revises: 0021_unified_audit
Create Date: 2026-11-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022_audit_actor_restrict"
down_revision: str | None = "0021_unified_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "audit_events_actor_user_id_fkey",
        "audit_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "audit_events_actor_user_id_fkey",
        "audit_events",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "audit_events_actor_user_id_fkey",
        "audit_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "audit_events_actor_user_id_fkey",
        "audit_events",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
