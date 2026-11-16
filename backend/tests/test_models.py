import pytest
from sqlalchemy import inspect

from app.models import Business, User


def test_user_table_contains_only_secure_auth_columns() -> None:
    columns = {column.name for column in inspect(User).columns}

    assert columns == {"id", "full_name", "email", "password_hash", "access_token"}
    assert "password" not in columns
    assert "has_business" not in columns


def test_business_table_tracks_owner_and_registration_time() -> None:
    columns = {column.name for column in inspect(Business).columns}
    foreign_keys = list(Business.__table__.c.owned_by.foreign_keys)

    assert columns == {"id", "name", "owned_by", "registered_on"}
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "users.id"


def test_has_business_is_derived_from_owned_businesses() -> None:
    user = User(
        full_name="Maya Chen",
        email="maya@example.com",
        password_hash="$argon2id$valid-example-hash",
        owned_businesses=[],
    )

    assert user.has_business is False

    user.owned_businesses.append(Business(name="Acme Studio"))

    assert user.has_business is True


def test_user_model_normalizes_names_and_email() -> None:
    user = User(
        full_name="  Maya   Chen  ",
        email=" MAYA@Example.COM ",
        password_hash="$argon2id$valid-example-hash",
    )

    assert user.full_name == "Maya Chen"
    assert user.email == "maya@example.com"


@pytest.mark.parametrize("email", ["not-an-email", "missing-domain@", "@example.com"])
def test_user_model_rejects_invalid_email(email: str) -> None:
    with pytest.raises(ValueError, match="Invalid email format"):
        User(
            full_name="Maya Chen",
            email=email,
            password_hash="$argon2id$valid-example-hash",
        )


def test_business_model_validates_name_and_owner() -> None:
    business = Business(name="  Acme   Studio  ", owned_by=1)

    assert business.name == "Acme Studio"
    assert business.owned_by == 1

    with pytest.raises(ValueError, match="Business name must be between"):
        Business(name=" ", owned_by=1)

    with pytest.raises(ValueError, match="positive user ID"):
        Business(name="Acme Studio", owned_by=0)


