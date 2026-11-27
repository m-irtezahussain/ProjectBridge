from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from app.api.auth_cookies import ACCESS_COOKIE
from app.config import get_settings
from app.core.services.mcp_oauth import MCP_SCOPES, ConsentClaims, OAuthProtocolError
from app.core.services.rate_limits import RateLimitExceededError
from app.deps import AuthManagerDep, AuthRateLimiterDep, OAuthManagerDep, SessionDep
from app.schemas.oauth import OAuthClientRegistrationRequest

router = APIRouter(tags=["mcp-oauth"])


def _oauth_error(exc: OAuthProtocolError, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.error, "error_description": exc.description},
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _append_query(url: str, **values: str) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(values.items())
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata() -> dict[str, object]:
    settings = get_settings()
    return {
        "resource": settings.mcp_resource,
        "authorization_servers": [settings.mcp_issuer],
        "bearer_methods_supported": ["header"],
        "scopes_supported": sorted(MCP_SCOPES),
    }


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata() -> dict[str, object]:
    settings = get_settings()
    issuer = settings.mcp_issuer.rstrip("/")
    return {
        "issuer": settings.mcp_issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "revocation_endpoint": f"{issuer}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": sorted(MCP_SCOPES),
    }


@router.post("/oauth/register", status_code=status.HTTP_201_CREATED)
async def register_client(
    request: Request,
    session: SessionDep,
    manager: OAuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> Response:
    try:
        client_host = request.client.host if request.client else "unknown"
        await limiter.consume(
            session, bucket="oauth-register-ip", identity=client_host, limit=20
        )
        data = OAuthClientRegistrationRequest.model_validate(await request.json())
        result = await manager.register_client(session, data)
    except RateLimitExceededError as exc:
        return _oauth_error(
            OAuthProtocolError("temporarily_unavailable", str(exc)),
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    except ValidationError as exc:
        return _oauth_error(
            OAuthProtocolError("invalid_client_metadata", exc.errors()[0]["msg"])
        )
    except (ValueError, TypeError):
        return _oauth_error(
            OAuthProtocolError("invalid_client_metadata", "Invalid JSON request")
        )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=result.model_dump(),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/oauth/authorize")
async def authorize_page(
    request: Request,
    session: SessionDep,
    manager: OAuthManagerDep,
    auth: AuthManagerDep,
) -> Response:
    query = request.query_params
    try:
        validated = await manager.validate_authorization_request(
            session,
            response_type=query.get("response_type", ""),
            client_id=query.get("client_id", ""),
            redirect_uri=query.get("redirect_uri", ""),
            scope=query.get("scope", ""),
            state=query.get("state", ""),
            code_challenge=query.get("code_challenge", ""),
            code_challenge_method=query.get("code_challenge_method", ""),
            resource=query.get("resource", ""),
        )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    user = await auth.get_user(session, request.cookies.get(ACCESS_COOKIE), "access")
    if user is None:
        settings = get_settings()
        return_to = f"{settings.mcp_issuer.rstrip('/')}{request.url.path}"
        if request.url.query:
            return_to = f"{return_to}?{request.url.query}"
        login_url = _append_query(
            f"{settings.web_url.rstrip('/')}/login", return_to=return_to
        )
        return RedirectResponse(login_url, status_code=status.HTTP_302_FOUND)
    claims = ConsentClaims(
        user_id=user.id,
        client_id=validated.client.client_id,
        redirect_uri=validated.redirect_uri,
        scopes=validated.scopes,
        state=validated.state,
        code_challenge=validated.code_challenge,
        resource=validated.resource,
    )
    consent_token = manager.issue_consent_token(claims)
    scopes = "".join(
        f"<li>{escape(scope)}</li>" for scope in validated.scopes.split()
    )
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Connect ProjectBridge</title></head><body>
<main><h1>Connect {escape(validated.client.client_name)} to ProjectBridge?</h1>
<p>Signed in as {escape(user.email)}. This client is requesting:</p><ul>{scopes}</ul>
<form method="post" action="/oauth/authorize">
<input type="hidden" name="consent_token" value="{escape(consent_token, quote=True)}">
<button type="submit" name="decision" value="approve">Allow</button>
<button type="submit" name="decision" value="deny">Cancel</button>
</form></main></body></html>"""
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        },
    )


@router.post("/oauth/authorize")
async def authorize_decision(
    request: Request,
    session: SessionDep,
    manager: OAuthManagerDep,
    auth: AuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> Response:
    form = await request.form()
    try:
        client_host = request.client.host if request.client else "unknown"
        await limiter.consume(
            session, bucket="oauth-consent-ip", identity=client_host, limit=30
        )
        claims = manager.decode_consent_token(str(form.get("consent_token", "")))
        validated = await manager.validate_authorization_request(
            session,
            response_type="code",
            client_id=claims.client_id,
            redirect_uri=claims.redirect_uri,
            scope=claims.scopes,
            state=claims.state,
            code_challenge=claims.code_challenge,
            code_challenge_method="S256",
            resource=claims.resource,
        )
    except RateLimitExceededError as exc:
        return _oauth_error(
            OAuthProtocolError("temporarily_unavailable", str(exc)),
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    user = await auth.get_user(session, request.cookies.get(ACCESS_COOKIE), "access")
    if user is None or user.id != claims.user_id:
        return _oauth_error(
            OAuthProtocolError("access_denied", "Authentication required"),
            status.HTTP_401_UNAUTHORIZED,
        )
    if form.get("decision") != "approve":
        return RedirectResponse(
            _append_query(
                validated.redirect_uri,
                error="access_denied",
                state=validated.state,
            ),
            status_code=status.HTTP_302_FOUND,
        )
    try:
        code = await manager.authorize(session, user_id=user.id, request=validated)
    except OAuthProtocolError as exc:
        return RedirectResponse(
            _append_query(
                validated.redirect_uri,
                error=exc.error,
                state=validated.state,
            ),
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        _append_query(validated.redirect_uri, code=code, state=validated.state),
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/oauth/token")
async def token(
    request: Request,
    session: SessionDep,
    manager: OAuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> Response:
    form = await request.form()
    grant_type = str(form.get("grant_type", ""))
    try:
        client_host = request.client.host if request.client else "unknown"
        client_id = str(form.get("client_id", ""))
        await limiter.consume(
            session, bucket="oauth-token-ip", identity=client_host, limit=100
        )
        await limiter.consume(
            session, bucket="oauth-token-client", identity=client_id, limit=60
        )
        if grant_type == "authorization_code":
            result = await manager.exchange_code(
                session,
                code=str(form.get("code", "")),
                client_id=client_id,
                redirect_uri=str(form.get("redirect_uri", "")),
                code_verifier=str(form.get("code_verifier", "")),
                resource=str(form.get("resource", "")),
            )
        elif grant_type == "refresh_token":
            scope_value = form.get("scope")
            result = await manager.refresh(
                session,
                refresh_token=str(form.get("refresh_token", "")),
                client_id=client_id,
                resource=str(form.get("resource", "")),
                requested_scope=str(scope_value) if scope_value is not None else None,
            )
        else:
            raise OAuthProtocolError(
                "unsupported_grant_type", "Unsupported OAuth grant type"
            )
    except RateLimitExceededError as exc:
        return _oauth_error(
            OAuthProtocolError("temporarily_unavailable", str(exc)),
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    return JSONResponse(
        result.model_dump(),
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/oauth/revoke")
async def revoke(
    request: Request,
    session: SessionDep,
    manager: OAuthManagerDep,
    limiter: AuthRateLimiterDep,
) -> Response:
    form = await request.form()
    try:
        client_host = request.client.host if request.client else "unknown"
        await limiter.consume(
            session, bucket="oauth-revoke-ip", identity=client_host, limit=60
        )
        await manager.revoke(
            session,
            token=str(form.get("token", "")),
            client_id=str(form.get("client_id", "")),
        )
    except RateLimitExceededError as exc:
        return _oauth_error(
            OAuthProtocolError("temporarily_unavailable", str(exc)),
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return Response(status_code=status.HTTP_200_OK, headers={"Cache-Control": "no-store"})
