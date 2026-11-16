from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="APP_ENV"
    )
    database_url: str = Field(
        default="postgresql+asyncpg://projectbridge:projectbridge-dev-only@db:5432/projectbridge",
        validation_alias="DATABASE_URL",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="APP_CORS_ORIGINS",
    )
    jwt_secret: str = Field(
        default="projectbridge-development-secret-change-before-production",
        min_length=32,
        validation_alias="APP_JWT_SECRET",
    )
    jwt_issuer: str = Field(
        default="projectbridge-api", validation_alias="APP_JWT_ISSUER"
    )
    jwt_audience: str = Field(
        default="projectbridge-web", validation_alias="APP_JWT_AUDIENCE"
    )
    jwt_access_minutes: int = Field(
        default=15, ge=5, le=60, validation_alias="APP_JWT_ACCESS_MINUTES"
    )
    refresh_sliding_days: int = Field(
        default=7, ge=1, le=30, validation_alias="APP_REFRESH_SLIDING_DAYS"
    )
    refresh_absolute_days: int = Field(
        default=30, ge=1, le=90, validation_alias="APP_REFRESH_ABSOLUTE_DAYS"
    )

    @model_validator(mode="after")
    def reject_development_secret_in_production(self) -> "Settings":
        if (
            self.environment == "production"
            and self.jwt_secret
            == "projectbridge-development-secret-change-before-production"
        ):
            raise ValueError("APP_JWT_SECRET must be set in production")
        if self.refresh_absolute_days < self.refresh_sliding_days:
            raise ValueError(
                "APP_REFRESH_ABSOLUTE_DAYS must be greater than or equal to "
                "APP_REFRESH_SLIDING_DAYS"
            )
        return self
    mcp_allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"],
        validation_alias="APP_MCP_ALLOWED_HOSTS",
    )
    mcp_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="APP_MCP_ALLOWED_ORIGINS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

