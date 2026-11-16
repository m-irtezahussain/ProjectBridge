from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import jwt

from app.config import Settings

TokenPurpose = Literal["access", "onboarding"]


class InvalidTokenError(ValueError):
    """Raised when a credential cannot be trusted."""


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    purpose: TokenPurpose


class TokenService:
    """Issue and validate short-lived, purpose-bound JWT credentials."""

    algorithm = "HS256"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def issue(self, user_id: int, purpose: TokenPurpose) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user_id),
            "purpose": purpose,
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.jwt_access_minutes),
            "jti": str(uuid4()),
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret,
            algorithm=self.algorithm,
            headers={"typ": "at+jwt" if purpose == "access" else "onboarding+jwt"},
        )

    def decode(self, token: str, purpose: TokenPurpose) -> TokenClaims:
        expected_type = "at+jwt" if purpose == "access" else "onboarding+jwt"
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != self.algorithm or header.get("typ") != expected_type:
                raise InvalidTokenError("Unexpected token header")
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self.algorithm],
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
                leeway=30,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "jti", "purpose"]},
            )
            if payload["purpose"] != purpose:
                raise InvalidTokenError("Unexpected token purpose")
            user_id = int(payload["sub"])
            if user_id < 1:
                raise InvalidTokenError("Invalid token subject")
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError("Invalid or expired credential") from exc
        return TokenClaims(user_id=user_id, purpose=purpose)
