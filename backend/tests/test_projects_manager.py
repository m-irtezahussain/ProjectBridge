from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.managers.projects import ProjectManager, ProjectNotFoundError
from app.core.services.mcp_auth import MCPPrincipal
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
        self,
        _session: object,
        business_id: int,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        return [
            project
            for project in self.items.values()
            if project.business_id == business_id
            and project.deleted_at is None
            and (status is None or project.status is status)
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
    session = AsyncMock()
    session.add = MagicMock()
    return manager, projects, session


async def test_project_crud_and_soft_dismissal() -> None:
    manager, projects, session = make_manager()

    created = await manager.create_project(
        session,
        "access-token",
        ProjectCreate(
            name="Client Portal",
            description="Initial delivery scope",
            status=ProjectStatus.ACTIVE,
        ),
    )
    updated = await manager.update_project(
        session,
        "access-token",
        created.id,
        ProjectUpdate(
            name="Customer Portal",
            description=None,
            status=ProjectStatus.AT_RISK,
        ),
    )

    assert created.business_id == 11
    assert updated.name == "Customer Portal"
    assert updated.description is None
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


async def test_mcp_principal_scopes_reads_to_its_server_resolved_business() -> None:
    manager, projects, session = make_manager()
    projects.items[1] = Project(
        id=1,
        name="Active project",
        business_id=11,
        status=ProjectStatus.ACTIVE,
    )
    projects.items[2] = Project(
        id=2,
        name="Planning project",
        business_id=11,
        status=ProjectStatus.PLANNING,
    )
    projects.items[3] = Project(
        id=3,
        name="Another tenant",
        business_id=999,
        status=ProjectStatus.ACTIVE,
    )
    principal = MCPPrincipal(
        user_id=1,
        business_id=11,
        scopes=frozenset({"projects:read"}),
        grant_id="grant-id",
    )

    listed = await manager.list_projects_for_principal(
        session, principal, ProjectStatus.ACTIVE
    )

    assert [project.id for project in listed] == [1]
    assert await manager.get_project_for_principal(session, principal, 1) is listed[0]
    with pytest.raises(ProjectNotFoundError):
        await manager.get_project_for_principal(session, principal, 3)
