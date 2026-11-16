import pytest
from sqlalchemy import inspect

from app.models import (
    Business,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskSource,
    TaskStatus,
    User,
)


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


def test_project_table_contains_tenant_status_and_soft_dismissal_columns() -> None:
    columns = {column.name for column in inspect(Project).columns}
    foreign_keys = list(Project.__table__.c.business_id.foreign_keys)

    assert columns == {
        "id",
        "name",
        "description",
        "business_id",
        "status",
        "deleted_at",
    }
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "business.id"


def test_project_model_normalizes_and_validates_fields() -> None:
    project = Project(
        name="  Client   Portal  ",
        description="  Coordinate   the client launch.  ",
        business_id=3,
        status=ProjectStatus.ACTIVE,
    )

    assert project.name == "Client Portal"
    assert project.description == "Coordinate the client launch."
    assert project.status is ProjectStatus.ACTIVE

    with pytest.raises(ValueError, match="Project name must be between"):
        Project(name=" ", business_id=3, status=ProjectStatus.PLANNING)
    with pytest.raises(ValueError, match="positive business ID"):
        Project(name="Client Portal", business_id=0, status=ProjectStatus.PLANNING)
    with pytest.raises(ValueError, match="Invalid project status"):
        Project(name="Client Portal", business_id=3, status="Paused")

    assert Project(
        name="Client Portal",
        description="   ",
        business_id=3,
        status=ProjectStatus.PLANNING,
    ).description is None


def test_task_table_contains_project_state_and_source_columns() -> None:
    columns = {column.name for column in inspect(Task).columns}
    foreign_keys = list(Task.__table__.c.project_id.foreign_keys)

    assert columns == {
        "id",
        "title",
        "description",
        "status",
        "priority",
        "project_id",
        "is_deleted",
        "created_by",
    }
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "projects.id"


def test_task_model_normalizes_and_validates_fields() -> None:
    task = Task(
        title="  Prepare   release notes ",
        description="  Capture   the final changes. ",
        status=TaskStatus.IN_REVIEW,
        priority=TaskPriority.HIGH,
        project_id=4,
        created_by=TaskSource.MCP,
    )

    assert task.title == "Prepare release notes"
    assert task.description == "Capture the final changes."
    assert task.status is TaskStatus.IN_REVIEW
    assert task.priority is TaskPriority.HIGH
    assert task.created_by is TaskSource.MCP

    with pytest.raises(ValueError, match="Task title must be between"):
        Task(title=" ", project_id=4)
    with pytest.raises(ValueError, match="positive project ID"):
        Task(title="Valid task", project_id=0)
    with pytest.raises(ValueError, match="Invalid task status"):
        Task(title="Valid task", project_id=4, status="blocked")
    with pytest.raises(ValueError, match="Invalid task priority"):
        Task(title="Valid task", project_id=4, priority="critical")
    with pytest.raises(ValueError, match="Invalid task source"):
        Task(title="Valid task", project_id=4, created_by="web")


