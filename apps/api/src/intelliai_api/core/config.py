"""Typed, environment-driven application settings.

Twelve-factor rules apply throughout:

- Environment variables are the only configuration channel. The ``.env`` file
  is a local-development convenience read from the working directory;
  production images contain no configuration files at all.
- Everything is validated once, at startup. A missing or malformed variable
  crashes the process with a precise error before it accepts traffic.
- Secrets are ``SecretStr``: they never appear in ``repr()``, logs, or
  tracebacks; code must explicitly call ``.get_secret_value()``.

Groups are separate ``BaseSettings`` classes, each with its own env prefix
(``INTELLIAI_DATABASE_URL``, ``INTELLIAI_STORAGE_ENDPOINT_URL`` …), composed
into one immutable ``Settings`` object.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "intelliai-api"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _group(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class DatabaseSettings(BaseSettings):
    model_config = _group("INTELLIAI_DATABASE_")

    url: SecretStr  # postgresql+asyncpg://user:password@host:port/dbname
    pool_size: int = 5
    pool_max_overflow: int = 10
    echo: bool = False


class RedisSettings(BaseSettings):
    model_config = _group("INTELLIAI_REDIS_")

    url: SecretStr  # redis://[:password@]host:port/db


class AuthSettings(BaseSettings):
    model_config = _group("INTELLIAI_AUTH_")

    # Server-side pepper mixed into API-key hashes. A database dump alone is
    # useless without it. No default: the platform refuses to boot unpeppered.
    # Rotating it invalidates EVERY issued key (accepted M1 debt, ADR-0012).
    key_pepper: SecretStr


class StorageSettings(BaseSettings):
    model_config = _group("INTELLIAI_STORAGE_")

    endpoint_url: str  # any S3-compatible endpoint (dev: MinIO)
    access_key: str
    secret_key: SecretStr
    region: str = "us-east-1"
    audio_bucket: str = "intelliai-audio"


class Settings(BaseSettings):
    """Root settings object; one instance per application instance."""

    model_config = _group("INTELLIAI_")

    env: Environment = Environment.DEV
    log_level: LogLevel = "INFO"

    auth: AuthSettings = Field(default_factory=AuthSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)

    @property
    def is_dev(self) -> bool:
        return self.env is Environment.DEV

    @property
    def is_prod(self) -> bool:
        return self.env is Environment.PROD


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, built once on first use.

    Only entrypoints (server startup, scripts) call this. Application code
    receives settings through dependency injection — tests inject their own
    ``Settings`` via ``create_app(settings=...)`` and never touch this cache.
    """
    return Settings()
