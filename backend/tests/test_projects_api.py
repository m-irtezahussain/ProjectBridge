from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.deps import get_project_manager
from app.main import create_app
from app.models import Project, ProjectStatus


class FakeProjectManager:
    def __init__(self) -> None:
        self.project = Project(
            id=4,
            name="Client Portal",
            description=None,
            business_id=7,
            status=ProjectStatus.PLANNING,
        )

    async def list_projects(self, _session: object, _token: str | None) -> list[Project]:
        return [self.project]

    async def get_project(
        self, _session: object, _token: str | None, _project_id: int
    ) -> Project:
        return self.project

    async def create_project(
        self, _session: object, _token: str | None, data: object
    ) -> Project:
        self.project.name = data.name  # type: ignore[attr-defined]
        self.project.description = data.description  # type: ignore[attr-defined]
        self.project.status = data.status  # type: ignore[attr-defined]
        return self.project

    async def update_project(
        self, _session: object, _token: str | None, _project_id: int, data: object
    ) -> Project:
        if data.name is not None:  # type: ignore[attr-defined]
            self.project.name = data.name  # type: ignore[attr-defined]
        if data.status is not None:  # type: ignore[attr-defined]
            self.project.status = data.status  # type: ignore[attr-defined]
        if "description" in data.model_fields_set:  # type: ignore[attr-defined]
            self.project.description = data.description  # type: ignore[attr-defined]
        return self.project

    async def dismiss_project(
        self, _session: object, _token: str | None, _project_id: int
    ) -> None:
        return None


async def fake_session() -> AsyncIterator[object]:
    yield object()


async def test_projects_crud_contract_and_validation() -> None:
    app = create_app()
    manager = FakeProjectManager()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_project_manager] = lambda: manager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listed = await client.get("/api/v1/projects")
        created = await client.post(
            "/api/v1/projects",
            json={
                "name": "  Launch   Site ",
                "description": "  Coordinate   the public launch. ",
                "status": "Active",
            },
        )
        updated = await client.patch(
            "/api/v1/projects/4",
            json={"status": "Completed"},
        )
        dismissed = await client.delete("/api/v1/projects/4")
        invalid = await client.post(
            "/api/v1/projects",
            json={"name": "A", "status": "Paused", "business_id": 999},
        )

    assert listed.status_code == 200
    assert listed.json()[0]["business_id"] == 7
    assert created.status_code == 201
    assert created.json()["name"] == "Launch Site"
    assert created.json()["description"] == "Coordinate the public launch."
    assert created.json()["status"] == "Active"
    assert updated.status_code == 200
    assert updated.json()["status"] == "Completed"
    assert dismissed.status_code == 204
    assert dismissed.content == b""
    assert invalid.status_code == 422
