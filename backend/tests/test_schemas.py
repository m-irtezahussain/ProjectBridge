import pytest
from pydantic import ValidationError

from app.schemas import BusinessCreate, UserCreate


def test_user_create_normalizes_valid_input() -> None:
    data = UserCreate(
        full_name="  Maya   Chen ",
        email=" MAYA@Example.COM ",
        password="a long memorable passphrase",
    )

    assert data.full_name == "Maya Chen"
    assert data.email == "maya@example.com"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_name", " "),
        ("email", "not-an-email"),
        ("password", "too short"),
    ],
)
def test_user_create_rejects_invalid_fields(field: str, value: str) -> None:
    payload = {
        "full_name": "Maya Chen",
        "email": "maya@example.com",
        "password": "a long memorable passphrase",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        UserCreate.model_validate(payload)


def test_user_create_rejects_mass_assignment() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UserCreate.model_validate(
            {
                "full_name": "Maya Chen",
                "email": "maya@example.com",
                "password": "a long memorable passphrase",
                "has_business": True,
            }
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UserCreate.model_validate(
            {
                "full_name": "Maya Chen",
                "email": "maya@example.com",
                "password": "a long memorable passphrase",
                "access_token": "client-controlled-token",
            }
        )


def test_business_create_normalizes_name_and_rejects_owner_override() -> None:
    assert BusinessCreate(name="  Acme   Studio ").name == "Acme Studio"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BusinessCreate.model_validate({"name": "Acme Studio", "owned_by": 999})


@pytest.mark.parametrize("name", ["", " ", "A", "A" * 201])
def test_business_create_rejects_invalid_name(name: str) -> None:
    with pytest.raises(ValidationError):
        BusinessCreate(name=name)

