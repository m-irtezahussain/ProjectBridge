from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.services.audit import AuditService
from app.core.services.mcp_oauth import (
    ConsentClaims,
    MCPTokenService,
    OAuthProtocolError,
    canonical_scopes,
    hash_credential,
    new_opaque_credential,
    validate_redirect_uri,
    verify_pkce,
)
from app.models import (
    ActionOrigin,
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthGrant,
    OAuthRefreshToken,
)
from app.repositories.businesses import BusinessRepository
from app.repositories.oauth import OAuthRepository
from app.schemas.oauth import (
    OAuthClientRegistrationRequest,
    OAuthClientRegistrationResponse,
    OAuthTokenResponse,
)


@dataclass(frozen=True)
class ValidatedAuthorizationRequest:
    client: OAuthClient
    redirect_uri: str
    scopes: str
    state: str
    code_challenge: str
    resource: str


class OAuthManager:
    """Implement ProjectBridge's OAuth authorization-code flow for MCP clients."""

    def __init__(
        self,
        settings: Settings,
        tokens: MCPTokenService,
        oauth: OAuthRepository | None = None,
        businesses: BusinessRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._settings = settings
        self._tokens = tokens
        self._oauth = oauth or OAuthRepository()
        self._businesses = businesses or BusinessRepository()
        self._audit = audit or AuditService()
        self._code_lifetime = timedelta(
            minutes=settings.mcp_authorization_code_minutes
        )
        self._refresh_lifetime = timedelta(days=settings.mcp_refresh_days)

    async def register_client(
        self, session: AsyncSession, data: OAuthClientRegistrationRequest
    ) -> OAuthClientRegistrationResponse:
        required_grants = {"authorization_code", "refresh_token"}
        if (
            not required_grants.issubset(data.grant_types)
            or "code" not in data.response_types
        ):
            raise OAuthProtocolError(
                "invalid_client_metadata",
                "Authorization-code and refresh grants with a code response are required",
            )
        redirect_uris = [
            validate_redirect_uri(
                uri, allow_http=self._settings.environment != "production"
            )
            for uri in data.redirect_uris
        ]
        client = OAuthClient(
            client_id=new_opaque_credential(),
            client_name=data.client_name.strip(),
            redirect_uris=redirect_uris,
        )
        if not client.client_name:
            raise OAuthProtocolError(
                "invalid_client_metadata", "client_name must not be blank"
            )
        self._oauth.add_client(session, client)
        await session.commit()
        return OAuthClientRegistrationResponse(
            client_id=client.client_id,
            client_name=client.client_name,
            redirect_uris=client.redirect_uris,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        )

    def issue_consent_token(self, claims: ConsentClaims) -> str:
        return self._tokens.issue_consent_token(claims)

    def decode_consent_token(self, token: str) -> ConsentClaims:
        return self._tokens.decode_consent_token(token)

    async def validate_authorization_request(
        self,
        session: AsyncSession,
        *,
        response_type: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: str,
        code_challenge_method: str,
        resource: str,
    ) -> ValidatedAuthorizationRequest:
        if response_type != "code":
            raise OAuthProtocolError(
                "unsupported_response_type", "Only response_type=code is supported"
            )
        if code_challenge_method != "S256":
            raise OAuthProtocolError(
                "invalid_request", "PKCE code_challenge_method must be S256"
            )
        if not 43 <= len(code_challenge) <= 128 or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for character in code_challenge
        ):
            raise OAuthProtocolError("invalid_request", "Invalid PKCE code challenge")
        if not state or len(state) > 1024:
            raise OAuthProtocolError("invalid_request", "A valid state value is required")
        if resource != self._settings.mcp_resource:
            raise OAuthProtocolError("invalid_target", "Unsupported OAuth resource")
        client = await self._oauth.get_client(session, client_id)
        if client is None:
            raise OAuthProtocolError("invalid_client", "Unknown OAuth client")
        if redirect_uri not in client.redirect_uris:
            raise OAuthProtocolError("invalid_request", "Redirect URI does not match")
        return ValidatedAuthorizationRequest(
            client=client,
            redirect_uri=redirect_uri,
            scopes=canonical_scopes(scope),
            state=state,
            code_challenge=code_challenge,
            resource=resource,
        )

    async def authorize(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        request: ValidatedAuthorizationRequest,
    ) -> str:
        business = await self._businesses.get_for_owner(session, user_id)
        if business is None:
            raise OAuthProtocolError(
                "access_denied", "A registered business is required"
            )
        grant_id = str(uuid4())
        raw_code = new_opaque_credential()
        grant = OAuthGrant(
            id=grant_id,
            user_id=user_id,
            client_id=request.client.client_id,
            resource=request.resource,
            scopes=request.scopes,
        )
        code = OAuthAuthorizationCode(
            code_hash=hash_credential(raw_code),
            grant_id=grant_id,
            client_id=request.client.client_id,
            redirect_uri=request.redirect_uri,
            code_challenge=request.code_challenge,
            expires_at=datetime.now(UTC) + self._code_lifetime,
        )
        self._oauth.add_grant_and_code(session, grant, code)
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=user_id,
            interface=ActionOrigin.REST,
            action="permission.grant",
            target_type="oauth_grant",
            target_id=None,
            outcome="success",
            details={
                "grant_id": grant.id,
                "client_id": grant.client_id,
                "scopes": grant.scopes.split(),
            },
        )
        await session.commit()
        return raw_code

    async def exchange_code(
        self,
        session: AsyncSession,
        *,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
        resource: str,
    ) -> OAuthTokenResponse:
        record = await self._oauth.get_code_for_update(
            session, hash_credential(code)
        )
        now = datetime.now(UTC)
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise OAuthProtocolError(
                "invalid_grant", "Invalid or expired authorization code"
            )
        grant = await self._oauth.get_grant(session, record.grant_id)
        valid = (
            grant is not None
            and grant.revoked_at is None
            and record.client_id == client_id
            and record.redirect_uri == redirect_uri
            and grant.resource == resource == self._settings.mcp_resource
            and verify_pkce(code_verifier, record.code_challenge)
        )
        record.used_at = now
        if not valid or grant is None:
            await self._oauth.revoke_grant(session, record.grant_id, now)
            await session.commit()
            raise OAuthProtocolError("invalid_grant", "Authorization code rejected")
        response = self._issue_tokens(grant, now=now)
        self._oauth.add_refresh_token(session, response[1])
        await session.commit()
        return response[0]

    async def refresh(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        client_id: str,
        resource: str,
        requested_scope: str | None,
    ) -> OAuthTokenResponse:
        record = await self._oauth.get_refresh_for_update(
            session, hash_credential(refresh_token)
        )
        now = datetime.now(UTC)
        if record is None:
            raise OAuthProtocolError("invalid_grant", "Invalid refresh token")
        grant = await self._oauth.get_grant(session, record.grant_id)
        if (
            record.used_at is not None
            or record.revoked_at is not None
            or record.expires_at <= now
            or grant is None
            or grant.revoked_at is not None
            or grant.client_id != client_id
            or grant.resource != resource
            or resource != self._settings.mcp_resource
        ):
            await self._oauth.revoke_refresh_family(session, record.family_id, now)
            await self._oauth.revoke_grant(session, record.grant_id, now)
            await session.commit()
            raise OAuthProtocolError("invalid_grant", "Invalid refresh token")
        token_scopes = grant.scopes
        if requested_scope is not None:
            requested = set(canonical_scopes(requested_scope).split())
            granted = set(grant.scopes.split())
            if not requested.issubset(granted):
                raise OAuthProtocolError(
                    "invalid_scope", "Requested scope exceeds the original grant"
                )
            token_scopes = " ".join(sorted(requested))
        record.used_at = now
        response, replacement = self._issue_tokens(
            grant,
            now=now,
            family_id=record.family_id,
            scopes=token_scopes,
        )
        record.replaced_by_token_hash = replacement.token_hash
        self._oauth.add_refresh_token(session, replacement)
        await session.commit()
        return response

    async def revoke(
        self,
        session: AsyncSession,
        *,
        token: str,
        client_id: str,
    ) -> None:
        now = datetime.now(UTC)
        refresh = await self._oauth.get_refresh_for_update(
            session, hash_credential(token)
        )
        if refresh is not None:
            grant = await self._oauth.get_grant(session, refresh.grant_id)
            if grant is not None and grant.client_id == client_id:
                await self._oauth.revoke_grant(session, grant.id, now)
                await self._audit_grant_revocation(session, grant)
                await session.commit()
            return
        try:
            claims = self._tokens.decode_access_token(token)
        except OAuthProtocolError:
            return
        if claims.client_id == client_id:
            grant = await self._oauth.get_grant(session, claims.grant_id)
            await self._oauth.revoke_grant(session, claims.grant_id, now)
            if grant is not None:
                await self._audit_grant_revocation(session, grant)
            await session.commit()

    async def _audit_grant_revocation(
        self, session: AsyncSession, grant: OAuthGrant
    ) -> None:
        business = await self._businesses.get_for_owner(session, grant.user_id)
        if business is None:
            return
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=grant.user_id,
            interface=ActionOrigin.REST,
            action="permission.revoke",
            target_type="oauth_grant",
            target_id=None,
            outcome="success",
            details={
                "grant_id": grant.id,
                "client_id": grant.client_id,
                "scopes": grant.scopes.split(),
            },
        )

    def _issue_tokens(
        self,
        grant: OAuthGrant,
        *,
        now: datetime,
        family_id: str | None = None,
        scopes: str | None = None,
    ) -> tuple[OAuthTokenResponse, OAuthRefreshToken]:
        raw_refresh = new_opaque_credential()
        refresh = OAuthRefreshToken(
            grant_id=grant.id,
            token_hash=hash_credential(raw_refresh),
            family_id=family_id or str(uuid4()),
            expires_at=now + self._refresh_lifetime,
        )
        token_scopes = scopes or grant.scopes
        access = self._tokens.issue_access_token(
            user_id=grant.user_id,
            grant_id=grant.id,
            client_id=grant.client_id,
            scopes=token_scopes,
        )
        return (
            OAuthTokenResponse(
                access_token=access,
                expires_in=int(self._tokens.access_lifetime.total_seconds()),
                refresh_token=raw_refresh,
                scope=token_scopes,
            ),
            refresh,
        )
