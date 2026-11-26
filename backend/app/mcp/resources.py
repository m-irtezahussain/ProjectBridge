from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from urllib.parse import quote

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError

from app.core.managers.documents import DocumentNotFoundError
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.managers.resources import ContextResourceManager, ResourcePage
from app.core.managers.tasks import TaskNotFoundError
from app.core.services.mcp_auth import MCPAuthenticationError, MCPAuthorizationError
from app.core.services.resource_cursor import ResourceCursorError
from app.mcp.auth import MCPDatabaseSessions, require_mcp_principal
from app.models import Document, Project, Task
from app.schemas.mcp_tools import MCPErrorDetail
from app.schemas.resources import (
    RESOURCE_MIME_TYPE,
    RESOURCE_SCHEMA_VERSION,
    CompactDocumentResource,
    CompactProjectResource,
    CompactTaskResource,
    ResourceCapabilities,
    ResourceLink,
    ResourcePageRepresentation,
)

PROJECTBRIDGE_MCP_VERSION = "0.1.0"


@asynccontextmanager
async def structured_resource_errors() -> AsyncIterator[None]:
    try:
        yield
    except (ProjectNotFoundError, TaskNotFoundError, DocumentNotFoundError) as error:
        detail = MCPErrorDetail(code="not_found", message=str(error))
        raise ResourceNotFoundError(detail.model_dump_json()) from error
    except ResourceCursorError as error:
        detail = MCPErrorDetail(code="validation_error", message=str(error))
        raise ResourceError(detail.model_dump_json()) from error
    except (MCPAuthenticationError, MCPAuthorizationError, BusinessRequiredError) as error:
        detail = MCPErrorDetail(code="authorization_error", message=str(error))
        raise ResourceError(detail.model_dump_json()) from error
    except ValueError as error:
        detail = MCPErrorDetail(code="validation_error", message=str(error))
        raise ResourceError(detail.model_dump_json()) from error


def _project(project: Project) -> CompactProjectResource:
    uri = f"projectbridge://projects/{project.id}"
    return CompactProjectResource(
        uri=uri,
        id=project.id,
        name=project.name,
        status=project.status.value,
        version=project.version,
        description_excerpt=(project.description[:500] if project.description else None),
        links=[
            ResourceLink(rel="tasks", uri=f"{uri}/tasks?limit=50"),
            ResourceLink(
                rel="documents",
                uri=f"projectbridge://documents?limit=50&project_id={project.id}",
            ),
        ],
    )


def _task(task: Task) -> CompactTaskResource:
    uri = f"projectbridge://projects/{task.project_id}/tasks/{task.id}"
    links = [
        ResourceLink(
            rel="project", uri=f"projectbridge://projects/{task.project_id}"
        )
    ]
    if task.source_document_id is not None:
        links.append(
            ResourceLink(
                rel="source-document",
                uri=f"projectbridge://documents/{task.source_document_id}",
            )
        )
    return CompactTaskResource(
        uri=uri,
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description_excerpt=(task.description[:500] if task.description else None),
        status=task.status.value,
        priority=task.priority.value,
        version=task.version,
        assignee_id=task.assignee_id,
        source_document_id=task.source_document_id,
        links=links,
    )


def _document(document: Document) -> CompactDocumentResource:
    uri = f"projectbridge://documents/{document.id}"
    links = []
    if document.project_id is not None:
        links.append(
            ResourceLink(
                rel="project", uri=f"projectbridge://projects/{document.project_id}"
            )
        )
    return CompactDocumentResource(
        uri=uri,
        id=document.id,
        project_id=document.project_id,
        filename=document.original_filename,
        status=document.status.value,
        version=document.version,
        mime_type=document.detected_mime_type or document.declared_mime_type,
        size_bytes=document.size_bytes,
        content_sha256=document.content_sha256,
        links=links,
    )


def _page_uri(
    base: str,
    *,
    limit: int,
    cursor: str | None,
    project_id: int | None = None,
) -> str:
    query = [f"limit={limit}"]
    if cursor is not None:
        query.append(f"cursor={quote(cursor, safe='')}")
    if project_id is not None:
        query.append(f"project_id={project_id}")
    return f"{base}?{'&'.join(query)}"


def _page_representation[ResourceItem](
    page: ResourcePage[ResourceItem],
    *,
    base_uri: str,
    limit: int,
    cursor: str | None,
    project_id: int | None,
    serialize: Callable[[ResourceItem], dict[str, object]],
) -> ResourcePageRepresentation:
    return ResourcePageRepresentation(
        uri=_page_uri(
            base_uri, limit=limit, cursor=cursor, project_id=project_id
        ),
        items=[serialize(item) for item in page.items],
        limit=limit,
        has_more=page.next_cursor is not None,
        next_cursor=page.next_cursor,
        next_uri=(
            _page_uri(
                base_uri,
                limit=limit,
                cursor=page.next_cursor,
                project_id=project_id,
            )
            if page.next_cursor is not None
            else None
        ),
    )


def register_context_resources(
    server: MCPServer,
    sessions: MCPDatabaseSessions,
    resources: ContextResourceManager,
) -> None:
    @server.resource(
        "projectbridge://capabilities",
        name="projectbridge-capabilities",
        title="ProjectBridge MCP capabilities",
        description="Resource schema, pagination, scopes, and safety documentation.",
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def capabilities() -> dict[str, object]:
        async with structured_resource_errors():
            require_mcp_principal()
        return ResourceCapabilities(
            server="ProjectBridge",
            server_version=PROJECTBRIDGE_MCP_VERSION,
            resource_schema_version=RESOURCE_SCHEMA_VERSION,
            mime_type=RESOURCE_MIME_TYPE,
            pagination={
                "method": "signed keyset cursor",
                "order": "id descending",
                "default_limit": 50,
                "maximum_limit": 100,
                "cursor_is_opaque": True,
            },
            safety={
                "tenant_scoped": True,
                "document_content_is_untrusted": True,
                "raw_documents_returned": False,
            },
            scopes={
                "projects": "projects:read",
                "tasks": "tasks:read",
                "documents": "documents:read",
                "audit_events": "audit:read",
            },
            templates=[
                {"name": "project", "uri": "projectbridge://projects/{project_id}"},
                {
                    "name": "project-page",
                    "uri": "projectbridge://projects{?limit,cursor}",
                },
                {
                    "name": "task",
                    "uri": "projectbridge://projects/{project_id}/tasks/{task_id}",
                },
                {
                    "name": "task-page",
                    "uri": "projectbridge://projects/{project_id}/tasks{?limit,cursor}",
                },
                {"name": "document", "uri": "projectbridge://documents/{document_id}"},
                {
                    "name": "document-page",
                    "uri": "projectbridge://documents{?limit,cursor,project_id}",
                },
            ],
        ).model_dump(mode="json")

    @server.resource(
        "projectbridge://projects/{project_id}",
        name="project-context",
        title="Project context",
        description="Compact tenant-scoped project metadata and related resource URIs.",
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def project_context(project_id: int) -> dict[str, object]:
        async with structured_resource_errors():
            principal = require_mcp_principal("projects:read")
            async with sessions.session() as session:
                project = await resources.get_project(session, principal, project_id)
        return _project(project).model_dump(mode="json")

    @server.resource(
        "projectbridge://projects{?limit,cursor}",
        name="project-context-page",
        title="Project context page",
        description="Cursor-paginated compact projects ordered by descending stable ID.",
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def project_context_page(
        limit: int = 50, cursor: str | None = None
    ) -> dict[str, object]:
        async with structured_resource_errors():
            principal = require_mcp_principal("projects:read")
            async with sessions.session() as session:
                page = await resources.list_projects(
                    session, principal, cursor=cursor, limit=limit
                )
        return _page_representation(
            page,
            base_uri="projectbridge://projects",
            limit=limit,
            cursor=cursor,
            project_id=None,
            serialize=lambda item: _project(item).model_dump(mode="json"),
        ).model_dump(mode="json")

    @server.resource(
        "projectbridge://projects/{project_id}/tasks/{task_id}",
        name="task-context",
        title="Task context",
        description="Compact tenant-scoped task metadata and source references.",
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def task_context(project_id: int, task_id: int) -> dict[str, object]:
        async with structured_resource_errors():
            principal = require_mcp_principal("tasks:read")
            async with sessions.session() as session:
                task = await resources.get_task(
                    session, principal, project_id, task_id
                )
        return _task(task).model_dump(mode="json")

    @server.resource(
        "projectbridge://projects/{project_id}/tasks{?limit,cursor}",
        name="task-context-page",
        title="Task context page",
        description="Cursor-paginated compact tasks ordered by descending stable ID.",
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def task_context_page(
        project_id: int, limit: int = 50, cursor: str | None = None
    ) -> dict[str, object]:
        async with structured_resource_errors():
            principal = require_mcp_principal("tasks:read")
            async with sessions.session() as session:
                page = await resources.list_tasks(
                    session,
                    principal,
                    project_id,
                    cursor=cursor,
                    limit=limit,
                )
        return _page_representation(
            page,
            base_uri=f"projectbridge://projects/{project_id}/tasks",
            limit=limit,
            cursor=cursor,
            project_id=None,
            serialize=lambda item: _task(item).model_dump(mode="json"),
        ).model_dump(mode="json")

    @server.resource(
        "projectbridge://documents/{document_id}",
        name="document-context",
        title="Document context",
        description="Compact document metadata without raw bytes or complete OCR text.",
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def document_context(document_id: int) -> dict[str, object]:
        async with structured_resource_errors():
            principal = require_mcp_principal("documents:read")
            async with sessions.session() as session:
                document = await resources.get_document(
                    session, principal, document_id
                )
        return _document(document).model_dump(mode="json")

    @server.resource(
        "projectbridge://documents{?limit,cursor,project_id}",
        name="document-context-page",
        title="Document context page",
        description=(
            "Cursor-paginated compact documents, optionally filtered by project, "
            "ordered by descending stable ID."
        ),
        mime_type=RESOURCE_MIME_TYPE,
    )
    async def document_context_page(
        limit: int = 50,
        cursor: str | None = None,
        project_id: int | None = None,
    ) -> dict[str, object]:
        async with structured_resource_errors():
            principal = require_mcp_principal("documents:read")
            async with sessions.session() as session:
                page = await resources.list_documents(
                    session,
                    principal,
                    project_id=project_id,
                    cursor=cursor,
                    limit=limit,
                )
        return _page_representation(
            page,
            base_uri="projectbridge://documents",
            limit=limit,
            cursor=cursor,
            project_id=project_id,
            serialize=lambda item: _document(item).model_dump(mode="json"),
        ).model_dump(mode="json")
