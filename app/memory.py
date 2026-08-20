import json
import sqlite3
from pathlib import Path

from .models import IncidentRecord


class IncidentMemory:
    """Local durable memory for human-recorded incident state and decisions."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")

    def _connect(self):
        return sqlite3.connect(self.path)

    def list(self) -> list[IncidentRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM incidents ORDER BY updated_at DESC").fetchall()
        return [IncidentRecord.model_validate_json(row[0]) for row in rows]

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return IncidentRecord.model_validate_json(row[0]) if row else None

    def put(self, record: IncidentRecord) -> IncidentRecord:
        payload = record.model_dump_json()
        with self._connect() as conn:
            conn.execute("""INSERT INTO incidents(id, payload, updated_at)
                VALUES(?, ?, datetime('now')) ON CONFLICT(id) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at""", (record.id, payload))
        return record
