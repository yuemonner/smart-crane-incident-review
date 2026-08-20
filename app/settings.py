from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).parents[1] / ".env", extra="ignore")
    aceco_demo_mode: bool = True
    ado_org: str = "AmericanCrane"
    ado_project: str = "Crane IoT"
    ado_pat: str | None = None
    aceco_source_root: str = "work/aceco_sources"
    aceco_notes_root: str = "C:/Users/Admin/Downloads"
    aceco_postgres_host: str | None = None
    aceco_postgres_port: int = 5432
    aceco_postgres_database: str = "api_edge"
    aceco_postgres_user: str | None = None
    aceco_postgres_password: str | None = None
    aceco_cloud_api_url: str = "https://pdacecofrontendrestapica.calmpebble-43b2067f.eastus.azurecontainerapps.io"
    incident_memory_path: str = "work/incident_memory.sqlite3"
    evidence_ledger_path: str = "work/evidence_ledger.sqlite3"
    telemetry_cache_path: str = "work/telemetry_cache.json"
    aceco_cosmos_host: str | None = None
    aceco_cosmos_port: int = 10350
    aceco_cosmos_username: str | None = None
    aceco_cosmos_password: str | None = None
    aceco_cosmos_keyspace: str = "cloud_core"


settings = Settings()
