from unittest.mock import AsyncMock

import pytest

from app.core.managers.projects import ProjectManager, ProjectNotFoundError
from app.models import Business, Project, ProjectStatus, User
from app.schemas import ProjectCreate, ProjectUpdate


class FakeAuth:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_user(
        self, _session: object, _token: str | None, _purpose: str
    ) -> User | None:
        return self.user


class FakeBusinesses:
    def __init__(self, business: Business | None) -> None:
        self.business = business

    async def get_for_owner(
        self, _session: object, owner_id: int
    ) -> Business | None:
        if self.business is None or self.business.owned_by != owner_id:
            return None
        return self.business


class FakeProjects:
    def __init__(self) -> None:
        self.items: dict[int, Project] = {}

    async def list_active(
        self, _session: object, business_id: int
    ) -> list[Project]:
        return [
            project
            for project in self.items.values()
            if project.business_id == business_id and project.deleted_at is None
        ]

    async def get_active(
        self, _session: object, business_id: int, project_id: int
    ) -> Project | None:
        project = self.items.get(project_id)
        if (
            project is None
            or project.business_id != business_id
            or project.deleted_at is not None
        ):
            return None
        return project

    def add(self, _session: object, project: Project) -> None:
        project.id = len(self.items) + 1
        self.items[project.id] = project


def make_manager() -> tuple[ProjectManager, FakeProjects, AsyncMock]:
    user = User(
        id=1,
        full_name="Maya Chen",
        email="maya@example.com",
        password_hash="$argon2id$valid-example-hash",
    )
    business = Business(id=11, name="Acme Studio", owned_by=1)
    projects = FakeProjects()
    manager = ProjectManager(
        FakeAuth(user),  # type: ignore[arg-type]
        FakeBusinesses(business),  # type: ignore[arg-type]
        projects,  # type: ignore[arg-type]
    )
    return manager, projects, AsyncMock()


async def test_project_crud_and_soft_dismissal() -> None:
    manager, projects, session = make_manager()

    created = await manager.create_project(
        session,
        "access-token",
        ProjectCreate(name="Client Portal", status=ProjectStatus.ACTIVE),
    )
    updated = await manager.update_project(
        session,
        "access-token",
        created.id,
        ProjectUpdate(name="Customer Portal", status=ProjectStatus.AT_RISK),
    )

    assert created.business_id == 11
    assert updated.name == "Customer Portal"
    assert updated.status is ProjectStatus.AT_RISK
    assert await manager.list_projects(session, "access-token") == [created]

    await manager.dismiss_project(session, "access-token", created.id)

    assert created.deleted_at is not None
    assert await manager.list_projects(session, "access-token") == []
    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        await manager.get_project(session, "access-token", created.id)
    assert projects.items[created.id] is created


async def test_project_lookup_never_crosses_business_boundary() -> None:
    manager, projects, session = make_manager()
    projects.items[9] = Project(
        id=9,
        name="Another tenant project",
        business_id=999,
        status=ProjectStatus.PLANNING,
    )

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        await manager.get_project(session, "access-token", 9)
