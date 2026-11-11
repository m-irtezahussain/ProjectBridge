"""Smoke-test the running MCP HTTP endpoint from inside the backend container."""

import json

import anyio
from mcp import Client


async def main() -> None:
    async with Client("http://localhost:8000/mcp/") as client:
        tools = await client.list_tools()
        result = await client.call_tool("get_service_status", {})

    assert [tool.name for tool in tools.tools] == ["get_service_status"]
    assert result.is_error is False
    print(json.dumps(result.structured_content, sort_keys=True))


if __name__ == "__main__":
    anyio.run(main)

