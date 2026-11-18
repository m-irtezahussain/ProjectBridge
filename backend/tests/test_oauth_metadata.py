from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.main import create_app


async def fake_session() -> AsyncIterator[object]:
    yield object()


async def test_oauth_discovery_advertises_pkce_refresh_and_mcp_resource() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resource = await client.get("/.well-known/oauth-protected-resource")
        authorization = await client.get("/.well-known/oauth-authorization-server")

    assert resource.status_code == 200
    assert resource.json()["resource"].endswith("/mcp/")
    assert authorization.status_code == 200
    assert authorization.json()["code_challenge_methods_supported"] == ["S256"]
    assert authorization.json()["grant_types_supported"] == [
        "authorization_code",
        "refresh_token",
    ]
