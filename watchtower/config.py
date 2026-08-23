from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://watchtower:watchtower@postgres:5432/watchtower"
    redis_url: str = "redis://redis:6379/0"
    watchtower_secret_key: SecretStr = Field(min_length=32)
    watchtower_encryption_key: SecretStr
    dashboard_url: str = "http://localhost:3000"
    min_check_interval: int = Field(default=60, ge=60)
    default_check_timeout: int = Field(default=30, ge=1, le=120)
    max_response_bytes: int = Field(default=10_000_000, ge=1024)
    snapshot_storage_path: Path = Path("/var/lib/watchtower/storage")
    ssrf_allow_private_networks: bool = False
    worker_concurrency: int = Field(default=4, ge=1, le=64)
    browser_concurrency: int = Field(default=2, ge=1, le=16)

    @field_validator("database_url")
    @classmethod
    def async_database_driver(cls, value: str) -> str:
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
