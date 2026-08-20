from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).parents[1] / ".env", extra="ignore")
    smart_crane_demo_mode: bool = True
    ado_org: str = "SmartCraneDemo"
    ado_project: str = "Crane IoT"
    ado_pat: str | None = None
    smart_crane_source_root: str = "work/smart_crane_sources"
    smart_crane_notes_root: str = "C:/Users/Admin/Downloads"
    smart_crane_postgres_host: str | None = None
    smart_crane_postgres_port: int = 5432
    smart_crane_postgres_database: str = "api_edge"
    smart_crane_postgres_user: str | None = None
    smart_crane_postgres_password: str | None = None
    smart_crane_cloud_api_url: str = "https://smart-crane-cloud.example.invalid"
    incident_memory_path: str = "work/incident_memory.sqlite3"
    evidence_ledger_path: str = "work/evidence_ledger.sqlite3"
    telemetry_cache_path: str = "work/telemetry_cache.json"
    smart_crane_cosmos_host: str | None = None
    smart_crane_cosmos_port: int = 10350
    smart_crane_cosmos_username: str | None = None
    smart_crane_cosmos_password: str | None = None
    smart_crane_cosmos_keyspace: str = "cloud_core"


settings = Settings()
