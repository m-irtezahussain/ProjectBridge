from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

from app.core.managers.auth import AuthenticationError
from app.db import get_session
from app.deps import get_task_manager
from app.main import create_app
from app.models import Task, TaskPriority, TaskSource, TaskStatus


class FakeTaskManager:
    def __init__(self) -> None:
        self.task = Task(
            id=5,
            title="Prepare release",
            description=None,
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            project_id=4,
            is_deleted=False,
            created_by=TaskSource.API,
        )

    async def list_tasks(
        self, _session: object, _token: str | None, _project_id: int
    ) -> list[Task]:
        return [self.task]

    async def get_task(
        self,
        _session: object,
        _token: str | None,
        _project_id: int,
        _task_id: int,
    ) -> Task:
        return self.task

    async def create_task(
        self,
        _session: object,
        _token: str | None,
        _project_id: int,
        data: object,
    ) -> Task:
        self.task.title = data.title  # type: ignore[attr-defined]
        self.task.description = data.description  # type: ignore[attr-defined]
        self.task.status = data.status  # type: ignore[attr-defined]
        self.task.priority = data.priority  # type: ignore[attr-defined]
        return self.task

    async def update_task(
        self,
        _session: object,
        _token: str | None,
        _project_id: int,
        _task_id: int,
        data: object,
    ) -> Task:
        for field in ("title", "description", "status", "priority"):
            if field in data.model_fields_set:  # type: ignore[attr-defined]
                setattr(self.task, field, getattr(data, field))
        return self.task

    async def dismiss_task(
        self,
        _session: object,
        _token: str | None,
        _project_id: int,
        _task_id: int,
    ) -> None:
        return None


async def fake_session() -> AsyncIterator[object]:
    yield object()


async def test_tasks_crud_contract_and_validation() -> None:
    app = create_app()
    manager = FakeTaskManager()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_task_manager] = lambda: manager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listed = await client.get("/api/v1/projects/4/tasks")
        fetched = await client.get("/api/v1/projects/4/tasks/5")
        created = await client.post(
            "/api/v1/projects/4/tasks",
            json={
                "title": "  Prepare   launch ",
                "description": "  Confirm   every dependency. ",
                "status": "in process",
                "priority": "high",
            },
        )
        updated = await client.patch(
            "/api/v1/projects/4/tasks/5", json={"status": "in review"}
        )
        dismissed = await client.delete("/api/v1/projects/4/tasks/5")
        invalid = await client.post(
            "/api/v1/projects/4/tasks",
            json={
                "title": "A",
                "status": "blocked",
                "project_id": 999,
                "created_by": "mcp",
            },
        )

    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert created.status_code == 201
    assert created.json() == {
        "id": 5,
        "title": "Prepare launch",
        "description": "Confirm every dependency.",
        "status": "in process",
        "priority": "high",
        "project_id": 4,
        "is_deleted": False,
        "created_by": "api",
    }
    assert updated.status_code == 200
    assert updated.json()["status"] == "in review"
    assert dismissed.status_code == 204
    assert invalid.status_code == 422


async def test_tasks_api_requires_authentication() -> None:
    class UnauthenticatedTaskManager(FakeTaskManager):
        async def list_tasks(
            self, _session: object, _token: str | None, _project_id: int
        ) -> list[Task]:
            raise AuthenticationError("Authentication required")

    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_task_manager] = UnauthenticatedTaskManager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/projects/4/tasks")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
