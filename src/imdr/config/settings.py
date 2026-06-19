from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Push .env into os.environ at import time. pydantic-settings already
# reads .env when populating Settings, but raw ``os.environ.get(...)``
# call sites (notably the playground/research/ingest_today_*.py daily
# scripts) need the values in the process env to see them. Doing this
# here means any module that imports Settings or get_settings inherits
# the loaded .env — single point of wiring.
load_dotenv(_PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IMDR_",
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MSSQL
    mssql_host: str = "localhost"
    mssql_port: int = 1433
    mssql_database: str = "IMDR"
    mssql_driver: str = "SQL+Server"  # legacy driver; required for DATETIMEOFFSET compat

    # Qdrant (vector DB) — local Windows Service install, see docs/admin/qdrant/
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str = ""  # empty = no auth (loopback-bound server only)
    qdrant_timeout: int = 30

    # Research RAG ingest — read by playground/research/ingest_today_*.py scripts.
    # Default OFF so a fresh checkout doesn't burn embedding spend by accident.
    research_embed: bool = False
    research_embed_model: str = "gemini-embedding-2"
    # Drop single-name equity research at discovery time (see
    # playground/research/ingest/relevance.py). Default ON — flip to
    # false via IMDR_RESEARCH_DROP_SINGLE_NAME_EQUITY=false in the
    # shell or .env for a one-off backfill that should pull single-name.
    research_drop_single_name_equity: bool = True
    # Inter-report pacing for research ingest. A random sleep in
    # [min, max] seconds is inserted before every ingest_one() call so
    # successive PDF downloads from the same vendor session look more
    # like a human reader than an automated firehose. Set max=0 to
    # disable. Apply per shell with IMDR_RESEARCH_PACING_SECONDS_MAX=0.
    research_pacing_seconds_min: float = 3.0
    research_pacing_seconds_max: float = 10.0

    # Connection Pool
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30

    # Read optimization
    mssql_read_pool_size: int = 10
    mssql_read_max_overflow: int = 20

    # Bulk ingestion
    bulk_batch_size: int = 5000

    # HTTP
    http_timeout: int = 30
    http_retries: int = 3

    # API Keys (per provider)
    bidfx_api_key: str = ""
    citivelocity_api_key: str = ""
    voyage_key: str = ""
    gemini_key: str = ""
    econ_fred_key: str = ""  # FRED (St. Louis Fed) — free key at https://fred.stlouisfed.org/docs/api/api_key.html

    # BidFX
    bidfx_username: str = ""
    bidfx_password: str = ""
    bidfx_base_url: str = "https://data.app.bidfx.com/api/price/historical/v1/fx"
    bidfx_max_workers: int = 16
    bidfx_timeout_connect: int = 3
    bidfx_timeout_read: int = 7

    # Citi Velocity (Rates)
    citi_host: str = "api.citivelocity.com"
    citi_client_id: str = ""
    citi_client_secret: str = ""
    # Separate credential pair for intraday/hourly pulls (separate quota bucket).
    # Fall back to primary creds if not set.
    citi_hourly_client_id: str = ""
    citi_hourly_client_secret: str = ""
    # Service-principal credentials for backfill runs (independent quota bucket).
    sp_client_id: str = ""
    sp_client_secret: str = ""
    citi_scope: str = "/api"
    citi_token_path: str = "/markets/cv/api/oauth2/token"
    citi_data_path: str = "/markets/analytics/chartingbe/rest/external/authed/data"
    citi_taglisting_path: str = "/markets/analytics/chartingbe/rest/external/authed/taglisting"
    citi_tagbrowsing_path: str = "/markets/analytics/chartingbe/rest/external/authed/tagbrowsing"
    citi_rate_limit_sec: float = 1.0
    citi_batch_size: int = 100
    citi_token_ttl: int = 3600
    citi_timeout: int = 60
    citi_tag_quota_limit: int = 95_000  # 5K safety margin below Citi's 100K hard limit
    citi_tag_quota_file: str = ""       # empty = data/cache/citi_tag_quota.json

    # Barclays Live (SKEW report downloads)
    barclays_url: str = "https://live.barcap.com"
    barclays_username: str = ""
    barclays_password: str = ""

    # Research portal auth (consumed by src/imdr/research/auth/).
    # JPM Janus portal needs a per-user "janus_user" GraphQL header in
    # addition to SSO cookies — username only, no password.
    research_jpm_username: str = ""

    # Programmatic-login credential pairs for the auth registry's
    # PROGRAMMATIC vendors. Loginflows at
    # src/imdr/research/auth/loginflows/{vendor}.py read these via
    # context._run_programmatic_login.cred_map.
    research_ubs_username: str = ""
    research_ubs_password: str = ""
    research_anz_username: str = ""
    research_anz_password: str = ""
    research_nomura_username: str = ""
    research_nomura_password: str = ""
    research_stanc_username: str = ""
    research_stanc_password: str = ""

    # Vendors framework
    browser_profile_root: Path = _PROJECT_ROOT / "data" / "browser_profiles"
    vendor_drop_root: Path = _PROJECT_ROOT / "data"

    # Email
    email_enabled: bool = False
    email_to: str = ""
    email_anomaly_to: str = ""
    # Macro release alerter (TE calendar 15-min digest). Falls back to email_to
    # when unset. Requires email_enabled AND te_alert_enabled.
    email_macro_to: str = ""
    te_alert_enabled: bool = False
    te_alert_importance_threshold: float = 66.0

    # Teams (Workflows webhook — "Post to a channel when a webhook request is received")
    teams_polymarket_webhook: str = ""

    # Anomaly
    anomaly_pct_threshold: float = 50.0

    # Parquet
    parquet_batch_dir: str = ""
    parquet_retention_days: int = 90

    # Run logs
    run_log_dir: str = ""

    # Cache
    cache_dir: str = ""

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
