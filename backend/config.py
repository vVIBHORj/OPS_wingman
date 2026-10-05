"""
Centralized Application Configuration for OpsWingman (Phase 5 Production Readiness).

Provides typed, validated settings using Pydantic Settings with strict separation
between safe development defaults and mandatory production validation.
"""

import json
from functools import lru_cache
from typing import Any, List, Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DEV_SECRET = "change-this-insecure-secret-key-for-local-dev-only"


class Settings(BaseSettings):
    """Platform configuration parameters loaded from environment and .env."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core Application
    app_name: str = Field(default="OpsWingman", description="Platform service name")
    environment: str = Field(default="development", description="Runtime environment: development, staging, production")
    log_level: str = Field(default="INFO", description="Logging verbosity level")
    debug: bool = Field(default=False, description="Debug mode toggle; must be False in production")

    # Network & Ingress
    backend_host: str = Field(default="0.0.0.0", description="Bind IP address for Uvicorn")
    backend_port: int = Field(default=8000, description="Listening TCP port for API")
    backend_cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins list or JSON array string",
    )

    # Database Settings
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/opswingman",
        description="Asynchronous SQLAlchemy connection URL",
    )
    database_sync_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/opswingman",
        description="Synchronous SQLAlchemy connection URL for Alembic and worker pools",
    )
    database_pool_size: int = Field(default=10, description="SQLAlchemy connection pool base size")
    database_max_overflow: int = Field(default=20, description="Max overflow connections allowed beyond pool_size")
    database_pool_timeout: int = Field(default=30, description="Seconds to wait before timing out on connection checkout")
    sql_echo: bool = Field(default=False, description="Log raw SQL statements")

    # Cache & Queue
    valkey_host: str = Field(default="localhost", description="Valkey/Redis hostname")
    valkey_port: int = Field(default=6379, description="Valkey/Redis port")
    valkey_url: str = Field(default="redis://localhost:6379/0", description="Valkey/Redis connection string")

    # Workflow Checkpoints
    checkpoint_dir: str = Field(default=".data/checkpoints", description="Directory path for local agent run checkpoints")

    # Security & Tokens
    app_secret_key: str = Field(
        default=DEFAULT_DEV_SECRET,
        description="Cryptographic secret key for token signing; required in production",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT hashing algorithm")
    access_token_expire_minutes: int = Field(default=60, description="Access token expiration window")
    docs_enabled: bool = Field(default=True, description="Expose OpenAPI documentation at /docs and /redoc")

    # Observability & Tracing (Optional / Stubs)
    langfuse_host: Optional[str] = Field(default=None, description="Langfuse host URL")
    langfuse_public_key: Optional[str] = Field(default=None, description="Langfuse public API key")
    langfuse_secret_key: Optional[str] = Field(default=None, description="Langfuse secret API key")
    langfuse_enable_telemetry: bool = Field(default=False, description="Send anonymous telemetry to Langfuse")
    otel_service_name: str = Field(default="opswingman-backend", description="OpenTelemetry service name")
    otel_exporter_otlp_endpoint: Optional[str] = Field(default=None, description="OTLP collector endpoint")

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parses CORS origins from JSON array string or comma-separated string."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(origin) for origin in v]
        return ["http://localhost:3000"]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforces security rules when running in production environment."""
        if self.environment.lower() == "production":
            if self.debug:
                raise ValueError("DEBUG must be set to False in production environment.")
            if self.app_secret_key == DEFAULT_DEV_SECRET or len(self.app_secret_key.strip()) < 16:
                raise ValueError(
                    "APP_SECRET_KEY must be set to a secure, non-default secret key of at least 16 characters in production."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns singleton instance of cached application settings."""
    return Settings()
