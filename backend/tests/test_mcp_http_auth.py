from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def test_mcp_http_endpoint_requires_a_bearer_token() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
    assert "resource_metadata=" in response.headers["www-authenticate"]
