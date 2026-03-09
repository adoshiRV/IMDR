from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IMDR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MSSQL
    mssql_host: str = "localhost"
    mssql_port: int = 1433
    mssql_database: str = "IMDR"
    mssql_driver: str = "ODBC+Driver+17+for+SQL+Server"

    # Connection Pool
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "console"

    @property
    def mssql_connection_url(self) -> str:
        """SQLAlchemy URL using Windows Authentication."""
        return (
            f"mssql+pyodbc://@{self.mssql_host}:{self.mssql_port}"
            f"/{self.mssql_database}"
            f"?driver={self.mssql_driver}"
            f"&Trusted_Connection=yes"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings factory for scripts and CLI entry points."""
    return Settings()
