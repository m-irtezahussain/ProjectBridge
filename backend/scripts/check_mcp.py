"""Smoke-test the running MCP HTTP endpoint from inside the backend container."""

import json
import os

import anyio
from mcp.client.session_group import ClientSessionGroup, StreamableHttpParameters


async def main() -> None:
    access_token = os.environ.get("PROJECTBRIDGE_MCP_ACCESS_TOKEN")
    if access_token is None:
        raise RuntimeError("PROJECTBRIDGE_MCP_ACCESS_TOKEN is required")
    parameters = StreamableHttpParameters(
        url="http://localhost:8000/mcp/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    async with ClientSessionGroup() as group:
        session = await group.connect_to_server(parameters)
        tools = await session.list_tools()
        result = await session.call_tool("get_service_status", {})

    assert [tool.name for tool in tools.tools] == [
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
    ]
    assert result.is_error is False
    print(json.dumps(result.structured_content, sort_keys=True))


if __name__ == "__main__":
    anyio.run(main)

