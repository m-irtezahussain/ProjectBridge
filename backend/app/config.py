from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
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
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://0.0.0.0:3000",
        ],
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
    web_url: str = Field(
        default="http://localhost:3000", validation_alias="APP_WEB_URL"
    )
    mcp_issuer: str = Field(
        default="http://localhost:8000", validation_alias="APP_MCP_ISSUER"
    )
    mcp_resource: str = Field(
        default="http://localhost:8000/mcp/", validation_alias="APP_MCP_RESOURCE"
    )
    mcp_jwt_secret: str = Field(
        default="projectbridge-mcp-development-secret-change-before-production",
        min_length=32,
        validation_alias="APP_MCP_JWT_SECRET",
    )
    mcp_access_minutes: int = Field(
        default=15, ge=5, le=60, validation_alias="APP_MCP_ACCESS_MINUTES"
    )
    mcp_refresh_days: int = Field(
        default=30, ge=1, le=90, validation_alias="APP_MCP_REFRESH_DAYS"
    )
    mcp_authorization_code_minutes: int = Field(
        default=5,
        ge=1,
        le=10,
        validation_alias="APP_MCP_AUTHORIZATION_CODE_MINUTES",
    )
    mcp_idempotency_lease_seconds: int = Field(
        default=60,
        ge=5,
        le=600,
        validation_alias="MCP_IDEMPOTENCY_LEASE_SECONDS",
    )
    mcp_idempotency_retention_hours: int = Field(
        default=168,
        ge=24,
        le=24 * 90,
        validation_alias="MCP_IDEMPOTENCY_RETENTION_HOURS",
    )
    mcp_idempotency_cleanup_batch: int = Field(
        default=500,
        ge=10,
        le=5000,
        validation_alias="MCP_IDEMPOTENCY_CLEANUP_BATCH",
    )
    s3_endpoint_url: str | None = Field(
        default=None, validation_alias="S3_ENDPOINT_URL"
    )
    s3_access_key_id: str | None = Field(
        default=None, validation_alias="S3_ACCESS_KEY_ID"
    )
    s3_secret_access_key: SecretStr | None = Field(
        default=None, validation_alias="S3_SECRET_ACCESS_KEY"
    )
    s3_bucket: str | None = Field(default=None, validation_alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", validation_alias="S3_REGION")
    s3_use_path_style: bool = Field(
        default=True, validation_alias="S3_USE_PATH_STYLE"
    )
    s3_presign_expiry_seconds: int = Field(
        default=300,
        ge=60,
        le=900,
        validation_alias="S3_PRESIGN_EXPIRY_SECONDS",
    )
    document_max_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1024,
        le=100 * 1024 * 1024,
        validation_alias="DOCUMENT_MAX_BYTES",
    )
    document_max_pages: int = Field(
        default=100, ge=1, le=1000, validation_alias="DOCUMENT_MAX_PAGES"
    )
    document_max_image_pixels: int = Field(
        default=40_000_000,
        ge=1_000_000,
        le=100_000_000,
        validation_alias="DOCUMENT_MAX_IMAGE_PIXELS",
    )
    document_max_image_dimension: int = Field(
        default=20_000,
        ge=1000,
        le=50_000,
        validation_alias="DOCUMENT_MAX_IMAGE_DIMENSION",
    )
    document_max_decompressed_bytes: int = Field(
        default=200 * 1024 * 1024,
        ge=1024 * 1024,
        le=500 * 1024 * 1024,
        validation_alias="DOCUMENT_MAX_DECOMPRESSED_BYTES",
    )
    ocr_model: str = Field(default="PP-OCRv6_small", validation_alias="OCR_MODEL")
    ocr_language: str = Field(default="en", validation_alias="OCR_LANGUAGE")
    ocr_worker_concurrency: int = Field(
        default=1, ge=1, le=4, validation_alias="OCR_WORKER_CONCURRENCY"
    )
    ocr_poll_seconds: float = Field(
        default=2.0, ge=0.25, le=30, validation_alias="OCR_POLL_SECONDS"
    )
    ocr_lease_seconds: int = Field(
        default=600, ge=60, le=3600, validation_alias="OCR_LEASE_SECONDS"
    )
    ocr_max_attempts: int = Field(
        default=5, ge=1, le=10, validation_alias="OCR_MAX_ATTEMPTS"
    )
    chroma_base_url: str | None = Field(
        default=None, validation_alias="CHROMA_BASE_URL"
    )
    chroma_tenant: str = Field(
        default="default_tenant", validation_alias="CHROMA_TENANT"
    )
    chroma_database: str = Field(
        default="default_database", validation_alias="CHROMA_DATABASE"
    )
    chroma_collection_prefix: str = Field(
        default="projectbridge", validation_alias="CHROMA_COLLECTION_PREFIX"
    )
    chroma_cf_access_client_id: str | None = Field(
        default=None, validation_alias="CHROMA_CF_ACCESS_CLIENT_ID"
    )
    chroma_cf_access_client_secret: SecretStr | None = Field(
        default=None, validation_alias="CHROMA_CF_ACCESS_CLIENT_SECRET"
    )
    chroma_timeout_seconds: float = Field(
        default=30.0, ge=1, le=120, validation_alias="CHROMA_TIMEOUT_SECONDS"
    )
    ollama_base_url: str | None = Field(
        default=None, validation_alias="OLLAMA_BASE_URL"
    )
    ollama_embedding_model: str | None = Field(
        default=None, validation_alias="OLLAMA_EMBEDDING_MODEL"
    )
    ollama_timeout_seconds: float = Field(
        default=60.0, ge=1, le=300, validation_alias="OLLAMA_TIMEOUT_SECONDS"
    )
    rag_chunk_characters: int = Field(
        default=1200, ge=200, le=8000, validation_alias="RAG_CHUNK_CHARACTERS"
    )
    rag_chunk_overlap_characters: int = Field(
        default=150, ge=0, le=2000, validation_alias="RAG_CHUNK_OVERLAP_CHARACTERS"
    )
    rag_worker_concurrency: int = Field(
        default=2, ge=1, le=8, validation_alias="RAG_WORKER_CONCURRENCY"
    )
    rag_poll_seconds: float = Field(
        default=2.0, ge=0.25, le=30, validation_alias="RAG_POLL_SECONDS"
    )
    rag_lease_seconds: int = Field(
        default=300, ge=30, le=3600, validation_alias="RAG_LEASE_SECONDS"
    )
    rag_max_attempts: int = Field(
        default=5, ge=1, le=10, validation_alias="RAG_MAX_ATTEMPTS"
    )

    @field_validator(
        "s3_endpoint_url",
        "s3_access_key_id",
        "s3_secret_access_key",
        "s3_bucket",
        "chroma_base_url",
        "chroma_cf_access_client_id",
        "chroma_cf_access_client_secret",
        "ollama_base_url",
        "ollama_embedding_model",
        mode="before",
    )
    @classmethod
    def normalize_optional_storage_setting(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_public_urls_and_mcp_secret(self) -> "Settings":
        for field_name in ("web_url", "mcp_issuer", "mcp_resource"):
            value = getattr(self, field_name)
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
            if parsed.username or parsed.password or parsed.fragment:
                raise ValueError(f"{field_name} must not contain credentials or a fragment")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError(f"{field_name} must use HTTPS in production")
        if self.environment == "production" and self.mcp_jwt_secret == (
            "projectbridge-mcp-development-secret-change-before-production"
        ):
            raise ValueError("APP_MCP_JWT_SECRET must be set in production")
        storage_values = (
            self.s3_endpoint_url,
            self.s3_access_key_id,
            self.s3_secret_access_key,
            self.s3_bucket,
        )
        if any(value is not None for value in storage_values) and not all(
            value is not None for value in storage_values
        ):
            raise ValueError(
                "S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, and "
                "S3_BUCKET must be configured together"
            )
        if self.environment == "production" and not all(
            value is not None for value in storage_values
        ):
            raise ValueError("S3 document storage must be configured in production")
        if self.s3_endpoint_url is not None:
            parsed = urlsplit(self.s3_endpoint_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("S3_ENDPOINT_URL must be an absolute HTTP(S) URL")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("S3_ENDPOINT_URL must not contain credentials or extras")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError("S3_ENDPOINT_URL must use HTTPS in production")
        rag_values = (
            self.chroma_base_url,
            self.chroma_cf_access_client_id,
            self.chroma_cf_access_client_secret,
            self.ollama_base_url,
            self.ollama_embedding_model,
        )
        if any(value is not None for value in rag_values) and not all(
            value is not None for value in rag_values
        ):
            raise ValueError(
                "CHROMA_BASE_URL, CHROMA_CF_ACCESS_CLIENT_ID, "
                "CHROMA_CF_ACCESS_CLIENT_SECRET, OLLAMA_BASE_URL, and "
                "OLLAMA_EMBEDDING_MODEL must be configured together"
            )
        if self.rag_chunk_overlap_characters >= self.rag_chunk_characters:
            raise ValueError(
                "RAG_CHUNK_OVERLAP_CHARACTERS must be smaller than "
                "RAG_CHUNK_CHARACTERS"
            )
        for field_name in ("chroma_base_url", "ollama_base_url"):
            value = getattr(self, field_name)
            if value is None:
                continue
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError(f"{field_name} must not contain credentials or extras")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError(f"{field_name} must use HTTPS in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

