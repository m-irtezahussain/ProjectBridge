import pytest
from mcp import Client

from app.mcp.server import mcp_server


@pytest.mark.asyncio
async def test_status_tool_contract() -> None:
    async with Client(mcp_server) as client:
        listed = await client.list_tools()
        result = await client.call_tool("get_service_status", {})

    assert [tool.name for tool in listed.tools] == [
        "get_service_status",
        "get_current_account",
        "list_projects",
        "get_project",
        "list_tasks",
        "get_task",
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
    ]
    tools = {tool.name: tool for tool in listed.tools}
    read_tools = {name: tools[name] for name in (
        "get_current_account",
        "list_projects",
        "get_project",
        "list_tasks",
        "get_task",
        "list_assignees",
        "list_documents",
        "get_document",
        "get_document_download_url",
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
    assert result.is_error is False
    assert result.structured_content == {
        "service": "projectbridge",
        "status": "ok",
        "version": "0.1.0",
    }

