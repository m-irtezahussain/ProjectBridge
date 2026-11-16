import pytest
from pydantic import ValidationError

from app.models import ProjectStatus, TaskPriority, TaskStatus
from app.schemas import (
    BusinessCreate,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskUpdate,
    UserCreate,
)


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


def test_project_create_normalizes_optional_description_and_defaults_status() -> None:
    project = ProjectCreate(
        name="  Client   Portal ",
        description="  Coordinate   the client launch. ",
    )

    assert project.name == "Client Portal"
    assert project.description == "Coordinate the client launch."
    assert project.status is ProjectStatus.PLANNING

    assert ProjectCreate(name="Client Portal", description="  ").description is None


@pytest.mark.parametrize("status", ["Paused", "active", "At Risk", ""])
def test_project_create_rejects_invalid_status(status: str) -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name="Client Portal", status=status)


def test_project_create_rejects_business_id_override() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProjectCreate.model_validate(
            {"name": "Client Portal", "status": "Active", "business_id": 999}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"status": None},
        {"name": "A"},
        {"status": "Paused"},
        {"description": "A" * 2001},
    ],
)
def test_project_update_rejects_empty_or_invalid_payloads(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate.model_validate(payload)


def test_task_create_normalizes_fields_and_uses_safe_defaults() -> None:
    task = TaskCreate(
        title="  Prepare   release notes ",
        description="  Capture   all changes. ",
    )

    assert task.title == "Prepare release notes"
    assert task.description == "Capture all changes."
    assert task.status is TaskStatus.TODO
    assert task.priority is TaskPriority.MEDIUM


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "A"},
        {"title": "Valid task", "status": "blocked"},
        {"title": "Valid task", "priority": "critical"},
        {"title": "Valid task", "description": "A" * 2001},
        {"title": "Valid task", "project_id": 999},
        {"title": "Valid task", "created_by": "mcp"},
        {"title": "Valid task", "is_deleted": True},
    ],
)
def test_task_create_rejects_invalid_or_server_owned_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        TaskCreate.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": None},
        {"status": None},
        {"priority": None},
        {"title": "A"},
        {"status": "blocked"},
        {"priority": "critical"},
        {"created_by": "mcp"},
    ],
)
def test_task_update_rejects_empty_invalid_or_server_owned_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(payload)

