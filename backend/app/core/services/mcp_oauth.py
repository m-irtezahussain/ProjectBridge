import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import jwt

from app.config import Settings

MCP_SCOPES = frozenset(
    {
        "projects:read",
        "projects:write",
        "tasks:read",
        "tasks:write",
        "documents:read",
        "documents:write",
        "search:read",
        "search:write",
        "offline_access",
    }
)
PKCE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


class OAuthProtocolError(ValueError):
    def __init__(self, error: str, description: str) -> None:
        super().__init__(description)
        self.error = error
        self.description = description


@dataclass(frozen=True)
class MCPAccessClaims:
    user_id: int
    grant_id: str
    client_id: str
    scopes: frozenset[str]
    expires_at: int


@dataclass(frozen=True)
class ConsentClaims:
    user_id: int
    client_id: str
    redirect_uri: str
    scopes: str
    state: str
    code_challenge: str
    resource: str


class MCPTokenService:
    """Issue and validate MCP access tokens and short-lived consent transactions."""

    algorithm = "HS256"
    consent_audience = "projectbridge-oauth-consent"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.access_lifetime = timedelta(minutes=settings.mcp_access_minutes)

    def issue_access_token(
        self,
        *,
        user_id: int,
        grant_id: str,
        client_id: str,
        scopes: str,
    ) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "iss": self._settings.mcp_issuer,
                "aud": self._settings.mcp_resource,
                "sub": str(user_id),
                "grant_id": grant_id,
                "client_id": client_id,
                "scope": scopes,
                "iat": now,
                "exp": now + self.access_lifetime,
                "jti": str(uuid4()),
            },
            self._settings.mcp_jwt_secret,
            algorithm=self.algorithm,
            headers={"typ": "at+jwt"},
        )

    def decode_access_token(self, token: str) -> MCPAccessClaims:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != self.algorithm or header.get("typ") != "at+jwt":
                raise OAuthProtocolError("invalid_token", "Invalid access token")
            payload = jwt.decode(
                token,
                self._settings.mcp_jwt_secret,
                algorithms=[self.algorithm],
                audience=self._settings.mcp_resource,
                issuer=self._settings.mcp_issuer,
                leeway=30,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "grant_id",
                        "client_id",
                        "scope",
                        "iat",
                        "exp",
                        "jti",
                    ]
                },
            )
            user_id = int(payload["sub"])
            if user_id < 1:
                raise ValueError
            scopes = parse_scopes(str(payload["scope"]))
            return MCPAccessClaims(
                user_id=user_id,
                grant_id=str(payload["grant_id"]),
                client_id=str(payload["client_id"]),
                scopes=scopes,
                expires_at=int(payload["exp"]),
            )
        except OAuthProtocolError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise OAuthProtocolError("invalid_token", "Invalid access token") from exc

    def issue_consent_token(self, claims: ConsentClaims) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "iss": self._settings.mcp_issuer,
                "aud": self.consent_audience,
                "sub": str(claims.user_id),
                "client_id": claims.client_id,
                "redirect_uri": claims.redirect_uri,
                "scope": claims.scopes,
                "state": claims.state,
                "code_challenge": claims.code_challenge,
                "resource": claims.resource,
                "iat": now,
                "exp": now + timedelta(minutes=10),
                "jti": str(uuid4()),
            },
            self._settings.mcp_jwt_secret,
            algorithm=self.algorithm,
            headers={"typ": "oauth-consent+jwt"},
        )

    def decode_consent_token(self, token: str) -> ConsentClaims:
        try:
            header = jwt.get_unverified_header(token)
            if (
                header.get("alg") != self.algorithm
                or header.get("typ") != "oauth-consent+jwt"
            ):
                raise ValueError
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.mcp_jwt_secret,
                algorithms=[self.algorithm],
                audience=self.consent_audience,
                issuer=self._settings.mcp_issuer,
                leeway=30,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "client_id",
                        "redirect_uri",
                        "scope",
                        "state",
                        "code_challenge",
                        "resource",
                        "iat",
                        "exp",
                        "jti",
                    ]
                },
            )
            return ConsentClaims(
                user_id=int(payload["sub"]),
                client_id=str(payload["client_id"]),
                redirect_uri=str(payload["redirect_uri"]),
                scopes=str(payload["scope"]),
                state=str(payload["state"]),
                code_challenge=str(payload["code_challenge"]),
                resource=str(payload["resource"]),
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise OAuthProtocolError(
                "invalid_request", "Invalid or expired consent transaction"
            ) from exc


def hash_credential(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_opaque_credential() -> str:
    return secrets.token_urlsafe(32)


def parse_scopes(value: str) -> frozenset[str]:
    scopes = frozenset(value.split())
    if not scopes or not scopes.issubset(MCP_SCOPES):
        raise OAuthProtocolError("invalid_scope", "Unsupported OAuth scope")
    return scopes


def canonical_scopes(value: str) -> str:
    return " ".join(sorted(parse_scopes(value)))


def validate_redirect_uri(uri: str, *, allow_http: bool) -> str:
    if len(uri) > 2048:
        raise OAuthProtocolError("invalid_redirect_uri", "Redirect URI is too long")
    parsed = urlsplit(uri)
    allowed_schemes = {"https"} | ({"http"} if allow_http else set())
    if (
        parsed.scheme not in allowed_schemes
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise OAuthProtocolError(
            "invalid_redirect_uri", "Redirect URI must be an absolute, safe URL"
        )
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise OAuthProtocolError(
            "invalid_redirect_uri", "HTTP redirect URIs are limited to loopback hosts"
        )
    return uri


def verify_pkce(code_verifier: str, expected_challenge: str) -> bool:
    if not PKCE_VERIFIER_PATTERN.fullmatch(code_verifier):
        return False
    digest = hashlib.sha256(code_verifier.encode()).digest()
    actual = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(actual, expected_challenge)
