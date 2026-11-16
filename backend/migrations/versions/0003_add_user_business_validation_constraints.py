"""Add user and business validation constraints.

Revision ID: 0003_validation_constraints
Revises: 0002_users_business
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_validation_constraints"
down_revision: str | None = "0002_users_business"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_full_name_length",
        "users",
        "char_length(btrim(full_name)) BETWEEN 2 AND 200",
    )
    op.create_check_constraint(
        "ck_users_email_shape",
        "users",
        "char_length(email) BETWEEN 3 AND 320 AND position('@' in email) > 1",
    )
    op.create_check_constraint(
        "ck_users_password_hash_argon2id",
        "users",
        "char_length(password_hash) BETWEEN 20 AND 255 "
        "AND password_hash LIKE '$argon2id$%'",
    )
    op.create_check_constraint(
        "ck_users_access_token_length",
        "users",
        "access_token IS NULL OR char_length(btrim(access_token)) BETWEEN 1 AND 2048",
    )
    op.create_check_constraint(
        "ck_business_name_length",
        "business",
        "char_length(btrim(name)) BETWEEN 2 AND 200",
    )
    op.create_check_constraint(
        "ck_business_owned_by_positive",
        "business",
        "owned_by > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_business_owned_by_positive", "business", type_="check")
    op.drop_constraint("ck_business_name_length", "business", type_="check")
    op.drop_constraint("ck_users_access_token_length", "users", type_="check")
    op.drop_constraint("ck_users_password_hash_argon2id", "users", type_="check")
    op.drop_constraint("ck_users_email_shape", "users", type_="check")
    op.drop_constraint("ck_users_full_name_length", "users", type_="check")

