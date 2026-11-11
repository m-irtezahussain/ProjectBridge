import pytest
from mcp import Client

from app.mcp.server import mcp_server


@pytest.mark.asyncio
async def test_status_tool_contract() -> None:
    async with Client(mcp_server) as client:
        listed = await client.list_tools()
        result = await client.call_tool("get_service_status", {})

    assert [tool.name for tool in listed.tools] == ["get_service_status"]
    assert result.is_error is False
    assert result.structured_content == {
        "service": "projectbridge",
        "status": "ok",
        "version": "0.1.0",
    }

