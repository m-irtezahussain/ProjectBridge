from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

from app.core.services.mcp_auth import AuthenticatedPrincipal
from app.db import get_session
from app.deps import get_task_manager, get_web_principal
from app.main import create_app
from app.models import ActionOrigin, Task, TaskPriority, TaskSource, TaskStatus

WEB_PRINCIPAL = AuthenticatedPrincipal(1, 7, frozenset(), "rest:1", ActionOrigin.REST)


class FakeTaskManager:
    def __init__(self) -> None:
        self.list_options: dict[str, object] = {}
        self.task = Task(
            id=5,
            title="Prepare release",
            description=None,
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            project_id=4,
            is_deleted=False,
            created_by=TaskSource.API,
            version=1,
        )

    async def list_tasks_page_for_principal(
        self,
        _session: object,
        _principal: object,
        _project_id: int,
        **options: object,
    ) -> tuple[list[Task], int]:
        self.list_options = options
        return [self.task], 1

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
    app.dependency_overrides[get_web_principal] = lambda: WEB_PRINCIPAL

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listed = await client.get(
            "/api/v1/projects/4/tasks?priority=medium&query=release&limit=10&sort_by=title&sort_order=asc"
        )
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
    assert listed.json()["tasks"][0]["id"] == 5
    assert listed.json()["total"] == 1
    assert manager.list_options == {
        "status": None,
        "priority": TaskPriority.MEDIUM,
        "assignee_id": None,
        "query": "release",
        "limit": 10,
        "offset": 0,
        "sort_by": "title",
        "descending": False,
    }
    assert fetched.status_code == 200
    assert created.status_code == 201
    assert created.json() == {
        "id": 5,
        "title": "Prepare launch",
        "description": "Confirm every dependency.",
        "status": "in process",
        "priority": "high",
        "assignee_id": None,
        "source_document_id": None,
        "source_candidate_id": None,
        "project_id": 4,
        "is_deleted": False,
        "created_by": "api",
        "version": 1,
    }
    assert updated.status_code == 200
    assert updated.json()["status"] == "in review"
    assert dismissed.status_code == 204
    assert invalid.status_code == 422


async def test_tasks_api_requires_authentication() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_task_manager] = FakeTaskManager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/projects/4/tasks")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
