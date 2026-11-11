from functools import lru_cache
from typing import Literal

from pydantic import Field
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

