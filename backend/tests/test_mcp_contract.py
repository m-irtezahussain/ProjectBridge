import pytest
from mcp import Client

from app.mcp.server import mcp_server


@pytest.mark.asyncio
async def test_status_tool_contract() -> None:
    async with Client(mcp_server) as client:
        listed = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        result = await client.call_tool("get_service_status", {})

    assert [tool.name for tool in listed.tools] == [
        "get_service_status",
        "get_current_account",
        "list_projects",
        "get_project",
        "list_tasks",
        "get_task",
        "get_task_source_reference",
        "list_assignees",
        "create_project",
        "update_project",
        "archive_project",
        "create_task",
        "update_task",
        "assign_task",
        "archive_task",
        "initiate_document_upload",
        "finalize_document_upload",
        "list_documents",
        "get_document",
        "get_document_download_url",
        "archive_document",
        "start_document_ingestion",
        "get_document_ingestion",
        "list_task_candidates",
        "confirm_task_candidates",
        "retry_document_ingestion",
        "search_project_knowledge",
        "reindex_project_knowledge",
    ]
    tools = {tool.name: tool for tool in listed.tools}
    read_tools = {name: tools[name] for name in (
        "get_current_account",
        "list_projects",
        "get_project",
        "list_tasks",
        "get_task",
        "get_task_source_reference",
        "list_assignees",
        "list_documents",
        "get_document",
        "get_document_download_url",
        "get_document_ingestion",
        "list_task_candidates",
        "search_project_knowledge",
    )}
    assert all(tool.annotations.read_only_hint is True for tool in read_tools.values())
    assert all(
        tool.annotations.destructive_hint is False for tool in read_tools.values()
    )
    assert tools["create_project"].annotations.idempotent_hint is True
    assert tools["create_task"].annotations.idempotent_hint is True
    assert tools["archive_task"].annotations.destructive_hint is True
    assert tools["archive_task"].annotations.idempotent_hint is True
    assert tools["archive_project"].annotations.idempotent_hint is True
    assert tools["archive_document"].annotations.idempotent_hint is True
    assert tools["finalize_document_upload"].annotations.idempotent_hint is True
    assert tools["start_document_ingestion"].annotations.idempotent_hint is True
    assert tools["retry_document_ingestion"].annotations.idempotent_hint is True
    assert result.is_error is False
    assert result.structured_content == {
        "service": "projectbridge",
        "status": "ok",
        "version": "0.1.0",
    }
    assert [(str(item.uri), item.mime_type) for item in resources.resources] == [
        (
            "projectbridge://capabilities",
            "application/vnd.projectbridge.context+json;version=1",
        )
    ]
    assert {template.uri_template for template in templates.resource_templates} == {
        "projectbridge://projects/{project_id}",
        "projectbridge://projects{?limit,cursor}",
        "projectbridge://projects/{project_id}/tasks/{task_id}",
        "projectbridge://projects/{project_id}/tasks{?limit,cursor}",
        "projectbridge://documents/{document_id}",
        "projectbridge://documents{?limit,cursor,project_id}",
    }
    assert all(
        template.mime_type
        == "application/vnd.projectbridge.context+json;version=1"
        for template in templates.resource_templates
    )

