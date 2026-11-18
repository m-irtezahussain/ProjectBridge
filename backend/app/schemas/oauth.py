from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _default_grant_types() -> list[Literal["authorization_code", "refresh_token"]]:
    return ["authorization_code", "refresh_token"]


def _default_response_types() -> list[Literal["code"]]:
    return ["code"]


class OAuthClientRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: str = Field(min_length=1, max_length=200)
    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    token_endpoint_auth_method: Literal["none"] = "none"
    grant_types: list[Literal["authorization_code", "refresh_token"]] = Field(
        default_factory=_default_grant_types
    )
    response_types: list[Literal["code"]] = Field(
        default_factory=_default_response_types
    )

    @field_validator("redirect_uris")
    @classmethod
    def unique_redirect_uris(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("redirect_uris must not contain duplicates")
        return values


class OAuthClientRegistrationResponse(BaseModel):
    client_id: str
    client_name: str
    redirect_uris: list[str]
    token_endpoint_auth_method: Literal["none"] = "none"
    grant_types: list[str]
    response_types: list[str]


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str


class OAuthErrorResponse(BaseModel):
    error: str
    error_description: str


class OAuthRevocationResponse(BaseModel):
    revoked: bool = True
