from fastapi import Response

from app.api.routers.auth import REFRESH_COOKIE, _set_refresh_cookie


def test_refresh_cookie_is_http_only_strict_and_auth_scoped() -> None:
    response = Response()

    _set_refresh_cookie(response, "opaque-refresh-token")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie
