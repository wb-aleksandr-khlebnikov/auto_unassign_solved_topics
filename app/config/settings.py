from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrySettings(BaseModel):
    timeout_seconds: float
    max_retries: int
    backoff_base: float
    backoff_max: float


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "discourse-assignee-automation"
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8080

    dry_run: bool = True

    discourse_base_url: str
    discourse_api_key: str
    discourse_api_username: str

    search_after_date: str = "2023-11-01"

    poll_interval_seconds: int = 300
    batch_size: int = 75
    history_retention_days: int = 180

    sqlite_path: str = "/data/state.db"

    http_timeout_seconds: float = 20.0
    http_max_retries: int = 5
    http_retry_backoff_base: float = 1.0
    http_retry_backoff_max: float = 20.0

    assign_unassign_endpoint: str = "/assign/unassign"
    assign_assign_endpoint: str = "/assign/assign"
    assign_payload_topic_key: str = "target_id"
    assign_payload_user_key: str = "username"
    assign_use_user_id: bool = False

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, value: int) -> int:
        if value < 50 or value > 100:
            raise ValueError("BATCH_SIZE must be between 50 and 100")
        return value

    @field_validator("poll_interval_seconds")
    @classmethod
    def validate_interval(cls, value: int) -> int:
        if value < 30:
            raise ValueError("POLL_INTERVAL_SECONDS must be >= 30")
        return value

    @property
    def retry(self) -> RetrySettings:
        return RetrySettings(
            timeout_seconds=self.http_timeout_seconds,
            max_retries=self.http_max_retries,
            backoff_base=self.http_retry_backoff_base,
            backoff_max=self.http_retry_backoff_max,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
