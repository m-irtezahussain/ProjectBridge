from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.core.managers import AccountManager, ProjectManager, TaskManager
from app.mcp.auth import MCPDatabaseSessions, require_mcp_principal
from app.models.project import ProjectStatus
from app.schemas.mcp_tools import (
    ArchiveTaskInput,
    ArchiveTaskResult,
    CreateProjectInput,
    CreateTaskInput,
    CurrentAccountSummary,
    ProjectListInput,
    ProjectListResult,
    ProjectMutationResult,
    ProjectSummary,
    TaskMutationResult,
    TaskSummary,
    UpdateProjectInput,
    UpdateTaskInput,
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
IDEMPOTENT_CREATE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
DESTRUCTIVE_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)


def register_read_tools(
    server: MCPServer,
    sessions: MCPDatabaseSessions,
    accounts: AccountManager,
    projects: ProjectManager,
) -> None:
    @server.tool(
        description=(
            "Return the connected ProjectBridge owner and business. Use this to confirm "
            "which account is active before working with projects or tasks."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_current_account() -> CurrentAccountSummary:
        principal = require_mcp_principal()
        async with sessions.session() as session:
            user, business = await accounts.get_current_account(session, principal)
        return CurrentAccountSummary(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            business_id=business.id,
            business_name=business.name,
            scopes=sorted(principal.scopes),
        )

    @server.tool(
        description=(
            "List active projects in the connected business, optionally filtered by "
            "project status. Never use a user-supplied business identifier."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_projects(
        status: ProjectStatus | None = None,
    ) -> ProjectListResult:
        data = ProjectListInput(status=status)
        principal = require_mcp_principal("projects:read")
        async with sessions.session() as session:
            items = await projects.list_projects_for_principal(
                session, principal, status=data.status
            )
        return ProjectListResult(
            projects=[ProjectSummary.model_validate(item) for item in items]
        )

    @server.tool(
        description=(
            "Get one active project by its stable ProjectBridge project ID. Use "
            "list_projects first when the ID is unknown."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_project(
        project_id: Annotated[int, Field(gt=0, description="Stable project ID")],
    ) -> ProjectSummary:
        principal = require_mcp_principal("projects:read")
        async with sessions.session() as session:
            project = await projects.get_project_for_principal(
                session, principal, project_id
            )
        return ProjectSummary.model_validate(project)


def register_write_tools(
    server: MCPServer,
    sessions: MCPDatabaseSessions,
    projects: ProjectManager,
    tasks: TaskManager,
) -> None:
    @server.tool(
        description=(
            "Create a project in the connected business. Reuse the same idempotency_key "
            "when retrying the same logical request; use a new key for a new project."
        ),
        annotations=IDEMPOTENT_CREATE,
        structured_output=True,
    )
    async def create_project(input: CreateProjectInput) -> ProjectMutationResult:
        principal = require_mcp_principal("projects:write")
        async with sessions.session() as session:
            result = await projects.create_project_for_principal(
                session,
                principal,
                input.project_data(),
                input.idempotency_key,
            )
        return ProjectMutationResult(
            project=ProjectSummary.model_validate(result.entity),
            replayed=result.replayed,
        )

    @server.tool(
        description=(
            "Update fields on one active project in the connected business. Use "
            "list_projects first when the stable project ID is unknown."
        ),
        annotations=WRITE,
        structured_output=True,
    )
    async def update_project(input: UpdateProjectInput) -> ProjectSummary:
        principal = require_mcp_principal("projects:write")
        async with sessions.session() as session:
            project = await projects.update_project_for_principal(
                session,
                principal,
                input.project_id,
                input.project_data(),
            )
        return ProjectSummary.model_validate(project)

    @server.tool(
        description=(
            "Create a task under an active project in the connected business. Reuse "
            "the same idempotency_key only when retrying the same logical request."
        ),
        annotations=IDEMPOTENT_CREATE,
        structured_output=True,
    )
    async def create_task(input: CreateTaskInput) -> TaskMutationResult:
        principal = require_mcp_principal("tasks:write")
        async with sessions.session() as session:
            result = await tasks.create_task_for_principal(
                session,
                principal,
                input.project_id,
                input.task_data(),
                input.idempotency_key,
            )
        return TaskMutationResult(
            task=TaskSummary.model_validate(result.entity),
            replayed=result.replayed,
        )

    @server.tool(
        description=(
            "Update fields on one active task. The project ID and task ID must both "
            "refer to records in the connected business."
        ),
        annotations=WRITE,
        structured_output=True,
    )
    async def update_task(input: UpdateTaskInput) -> TaskSummary:
        principal = require_mcp_principal("tasks:write")
        async with sessions.session() as session:
            task = await tasks.update_task_for_principal(
                session,
                principal,
                input.project_id,
                input.task_id,
                input.task_data(),
            )
        return TaskSummary.model_validate(task)

    @server.tool(
        description=(
            "Archive one active task by soft deletion. This is destructive from the "
            "user's perspective and must only be used after explicit confirmation."
        ),
        annotations=DESTRUCTIVE_WRITE,
        structured_output=True,
    )
    async def archive_task(input: ArchiveTaskInput) -> ArchiveTaskResult:
        principal = require_mcp_principal("tasks:write")
        async with sessions.session() as session:
            await tasks.archive_task_for_principal(
                session, principal, input.project_id, input.task_id
            )
        return ArchiveTaskResult(task_id=input.task_id, archived=True)
