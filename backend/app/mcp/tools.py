from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from app.core.managers import AccountManager, ProjectManager, TaskManager
from app.core.managers.accounts import AccountNotFoundError
from app.core.managers.auth import AuthenticationError
from app.core.managers.documents import (
    DocumentNotFoundError,
    DocumentStateConflictError,
)
from app.core.managers.ingestion import IngestionConflictError, IngestionNotFoundError
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.managers.search import SearchConflictError
from app.core.managers.tasks import AssigneeNotFoundError, TaskNotFoundError
from app.core.services.document_storage import DocumentStorageError
from app.core.services.document_validation import DocumentValidationError
from app.core.services.embeddings import EmbeddingServiceError
from app.core.services.mcp_auth import MCPAuthenticationError, MCPAuthorizationError
from app.core.services.mcp_mutations import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
)
from app.core.services.vector_store import VectorStoreError
from app.mcp.auth import MCPDatabaseSessions, require_mcp_principal
from app.models.project import ProjectStatus
from app.schemas.mcp_tools import (
    ArchiveProjectInput,
    ArchiveProjectResult,
    ArchiveTaskInput,
    ArchiveTaskResult,
    AssigneeListResult,
    AssigneeSummary,
    AssignTaskInput,
    CreateProjectInput,
    CreateTaskInput,
    CurrentAccountSummary,
    MCPErrorDetail,
    ProjectListInput,
    ProjectListResult,
    ProjectMutationResult,
    ProjectSummary,
    TaskListInput,
    TaskListResult,
    TaskMutationResult,
    TaskSourceReference,
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
IDEMPOTENT_WRITE = ToolAnnotations(
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
IDEMPOTENT_DESTRUCTIVE_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=False,
)


@asynccontextmanager
async def structured_mcp_errors() -> AsyncIterator[None]:
    """Translate shared-core failures into a stable machine-readable MCP error."""
    try:
        yield
    except ValidationError as error:
        detail = MCPErrorDetail(
            code="validation_error",
            message="Invalid tool input",
        )
        raise ToolError(detail.model_dump_json()) from error
    except DocumentValidationError as error:
        detail = MCPErrorDetail(code="validation_error", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except MCPAuthenticationError as error:
        detail = MCPErrorDetail(code="authentication_error", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except (MCPAuthorizationError, AuthenticationError, BusinessRequiredError) as error:
        detail = MCPErrorDetail(code="authorization_error", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except (
        AccountNotFoundError,
        DocumentNotFoundError,
        IngestionNotFoundError,
        ProjectNotFoundError,
        TaskNotFoundError,
    ) as error:
        detail = MCPErrorDetail(code="not_found", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except AssigneeNotFoundError as error:
        detail = MCPErrorDetail(code="validation_error", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except (IdempotencyConflictError, IdempotencyInProgressError) as error:
        detail = MCPErrorDetail(code="conflict", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except (
        DocumentStateConflictError,
        IngestionConflictError,
        SearchConflictError,
    ) as error:
        detail = MCPErrorDetail(code="conflict", message=str(error))
        raise ToolError(detail.model_dump_json()) from error
    except (EmbeddingServiceError, VectorStoreError) as error:
        detail = MCPErrorDetail(
            code="service_unavailable",
            message="Project knowledge search is temporarily unavailable",
            retryable=True,
        )
        raise ToolError(detail.model_dump_json()) from error
    except DocumentStorageError as error:
        detail = MCPErrorDetail(
            code="conflict",
            message="Document storage is temporarily unavailable",
            retryable=True,
        )
        raise ToolError(detail.model_dump_json()) from error


def register_read_tools(
    server: MCPServer,
    sessions: MCPDatabaseSessions,
    accounts: AccountManager,
    projects: ProjectManager,
    tasks: TaskManager,
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
        async with structured_mcp_errors():
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
        query: str | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        sort_by: Literal["id", "name", "status"] = "id",
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> ProjectListResult:
        async with structured_mcp_errors():
            data = ProjectListInput(
                status=status,
                query=query,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            principal = require_mcp_principal("projects:read")
            async with sessions.session() as session:
                items, total = await projects.list_projects_page_for_principal(
                    session,
                    principal,
                    status=data.status,
                    query=data.query,
                    limit=data.limit,
                    offset=data.offset,
                    sort_by=data.sort_by,
                    descending=data.sort_order == "desc",
                )
        return ProjectListResult(
            projects=[ProjectSummary.model_validate(item) for item in items],
            total=total,
            limit=data.limit,
            offset=data.offset,
            has_more=data.offset + len(items) < total,
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
        async with structured_mcp_errors():
            principal = require_mcp_principal("projects:read")
            async with sessions.session() as session:
                project = await projects.get_project_for_principal(
                    session, principal, project_id
                )
        return ProjectSummary.model_validate(project)

    @server.tool(
        description=(
            "List active tasks in one project with tenant-safe filters, pagination, "
            "and deterministic sorting."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_tasks(input: TaskListInput) -> TaskListResult:
        async with structured_mcp_errors():
            principal = require_mcp_principal("tasks:read")
            async with sessions.session() as session:
                items, total = await tasks.list_tasks_page_for_principal(
                    session,
                    principal,
                    input.project_id,
                    status=input.status,
                    priority=input.priority,
                    assignee_id=input.assignee_id,
                    query=input.query,
                    limit=input.limit,
                    offset=input.offset,
                    sort_by=input.sort_by,
                    descending=input.sort_order == "desc",
                )
        return TaskListResult(
            tasks=[TaskSummary.model_validate(item) for item in items],
            total=total,
            limit=input.limit,
            offset=input.offset,
            has_more=input.offset + len(items) < total,
        )

    @server.tool(
        description="Get one active task in a project by stable task ID.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_task(
        project_id: Annotated[int, Field(gt=0)],
        task_id: Annotated[int, Field(gt=0)],
    ) -> TaskSummary:
        async with structured_mcp_errors():
            principal = require_mcp_principal("tasks:read")
            async with sessions.session() as session:
                task = await tasks.get_task_for_principal(
                    session, principal, project_id, task_id
                )
        return TaskSummary.model_validate(task)

    @server.tool(
        description=(
            "Get compact document and OCR provenance for a task without returning "
            "the raw file or complete extracted document text."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_task_source_reference(
        project_id: Annotated[int, Field(gt=0)],
        task_id: Annotated[int, Field(gt=0)],
    ) -> TaskSourceReference:
        async with structured_mcp_errors():
            principal = require_mcp_principal("tasks:read", "documents:read")
            async with sessions.session() as session:
                reference = await tasks.get_source_reference_for_principal(
                    session, principal, project_id, task_id
                )
        document = reference.document
        candidate = reference.candidate
        text = reference.document_text
        run = reference.ingestion_run
        return TaskSourceReference(
            task_id=reference.task.id,
            project_id=reference.task.project_id,
            task_created_via=reference.task.created_by,
            has_document_source=document is not None,
            document_id=document.id if document else None,
            document_project_id=document.project_id if document else None,
            original_filename=document.original_filename if document else None,
            content_sha256=document.content_sha256 if document else None,
            candidate_id=candidate.id if candidate else None,
            ingestion_run_id=run.id if run else None,
            source_excerpt=candidate.source_excerpt if candidate else None,
            page_number=candidate.page_number if candidate else None,
            source_line_start=candidate.source_line_start if candidate else None,
            source_line_end=candidate.source_line_end if candidate else None,
            extractor=candidate.extractor if candidate else None,
            extractor_version=candidate.extractor_version if candidate else None,
            extracted_via=candidate.extracted_via if candidate else None,
            ocr_status=(text.status.value if text else run.ocr_status.value if run else None),
            ocr_engine=text.engine if text else None,
            ocr_engine_version=text.engine_version if text else None,
            ocr_model=text.model if text else None,
            ocr_language=text.language if text else None,
            ingestion_initiated_by_user_id=run.requested_by_user_id if run else None,
            ingestion_initiated_via=run.initiated_via if run else None,
        )

    @server.tool(
        description=(
            "List users in the connected business who may be assigned tasks. Use "
            "the returned user_id for task assignment or reassignment."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_assignees() -> AssigneeListResult:
        async with structured_mcp_errors():
            principal = require_mcp_principal("tasks:read")
            async with sessions.session() as session:
                assignees = await tasks.list_assignees_for_principal(
                    session, principal
                )
        return AssigneeListResult(
            assignees=[
                AssigneeSummary(
                    user_id=item.id,
                    full_name=item.full_name,
                    email=item.email,
                )
                for item in assignees
            ]
        )


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
        async with structured_mcp_errors():
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
        async with structured_mcp_errors():
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
            "Archive a project by soft deletion. Retrying the same project ID is "
            "safe and returns replayed=true."
        ),
        annotations=IDEMPOTENT_DESTRUCTIVE_WRITE,
        structured_output=True,
    )
    async def archive_project(input: ArchiveProjectInput) -> ArchiveProjectResult:
        async with structured_mcp_errors():
            principal = require_mcp_principal("projects:write")
            async with sessions.session() as session:
                replayed = await projects.archive_project_for_principal(
                    session, principal, input.project_id
                )
        return ArchiveProjectResult(
            project_id=input.project_id, archived=True, replayed=replayed
        )

    @server.tool(
        description=(
            "Create a task under an active project in the connected business. Reuse "
            "the same idempotency_key only when retrying the same logical request."
        ),
        annotations=IDEMPOTENT_CREATE,
        structured_output=True,
    )
    async def create_task(input: CreateTaskInput) -> TaskMutationResult:
        async with structured_mcp_errors():
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
        async with structured_mcp_errors():
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
            "Assign or reassign one active task to a user returned by "
            "list_assignees. The assignee must belong to the connected business."
        ),
        annotations=WRITE,
        structured_output=True,
    )
    async def assign_task(input: AssignTaskInput) -> TaskSummary:
        async with structured_mcp_errors():
            principal = require_mcp_principal("tasks:write")
            async with sessions.session() as session:
                task = await tasks.assign_task_for_principal(
                    session,
                    principal,
                    input.project_id,
                    input.task_id,
                    input.assignee_id,
                )
        return TaskSummary.model_validate(task)

    @server.tool(
        description=(
            "Archive one active task by soft deletion. This is destructive from the "
            "user's perspective and must only be used after explicit confirmation."
        ),
        annotations=IDEMPOTENT_DESTRUCTIVE_WRITE,
        structured_output=True,
    )
    async def archive_task(input: ArchiveTaskInput) -> ArchiveTaskResult:
        async with structured_mcp_errors():
            principal = require_mcp_principal("tasks:write")
            async with sessions.session() as session:
                replayed = await tasks.archive_task_for_principal(
                    session, principal, input.project_id, input.task_id
                )
        return ArchiveTaskResult(
            task_id=input.task_id, archived=True, replayed=replayed
        )
