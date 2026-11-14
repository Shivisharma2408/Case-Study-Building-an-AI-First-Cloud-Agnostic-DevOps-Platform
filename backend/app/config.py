"""Runtime configuration, read exclusively from environment variables.

The database can be configured either with a single ``DATABASE_URL`` or with the
discrete ``DB_*`` variables. The discrete form is what the Kubernetes Secret
(created by Terraform's ``app`` module) provides, so swapping the in-cluster
PostgreSQL for a managed one (RDS, Cloud SQL, ...) only changes Secret values.
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ideas"
    db_user: str = "ideas"
    db_password: str = ""
    db_sslmode: str = "prefer"
    db_connect_timeout_seconds: float = Field(default=60.0, ge=0)

    max_idea_length: int = Field(default=500, ge=1, le=10_000)
    log_level: str = "INFO"

    # Pipeline runs directory (artifacts/runs). Unset: /api/pipelines reports no runs.
    pipeline_runs_dir: str | None = None

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg://{user}:{password}@{self.db_host}:{self.db_port}/"
            f"{self.db_name}?sslmode={self.db_sslmode}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
