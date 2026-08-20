import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import EvidenceEvent


class EvidenceLedger:
    """Append-only local evidence index with a verifiable hash chain.

    This makes accidental mutation detectable inside this application. It is not
    a hardware-backed immutable store and does not establish legal chain of custody.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS evidence_ledger (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL UNIQUE,
                appended_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            )""")

    def _connect(self):
        return sqlite3.connect(self.path)

    def append(self, event: EvidenceEvent) -> dict:
        payload = event.model_dump_json(exclude_none=False)
        with self._connect() as conn:
            existing = conn.execute("SELECT sequence, entry_hash FROM evidence_ledger WHERE evidence_id=?",
                                    (event.id,)).fetchone()
            if existing:
                return {"sequence": existing[0], "entry_hash": existing[1], "added": False}
            previous = conn.execute("SELECT entry_hash FROM evidence_ledger ORDER BY sequence DESC LIMIT 1").fetchone()
            previous_hash = previous[0] if previous else "GENESIS"
            digest = hashlib.sha256((previous_hash + payload).encode()).hexdigest()
            appended_at = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute("""INSERT INTO evidence_ledger
                (evidence_id, appended_at, payload, previous_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?)""", (event.id, appended_at, payload, previous_hash, digest))
            return {"sequence": cursor.lastrowid, "entry_hash": digest, "added": True}

    def status(self) -> dict:
        valid, count, head = self.verify()
        return {"entries": count, "chain_valid": valid, "head_hash": head,
                "limitation": "Application-level hash chain only; source immutability and legal chain of custody are not established."}

    def verify(self) -> tuple[bool, int, str | None]:
        previous = "GENESIS"
        count = 0
        head = None
        with self._connect() as conn:
            rows = conn.execute("SELECT payload, previous_hash, entry_hash FROM evidence_ledger ORDER BY sequence").fetchall()
        for payload, stored_previous, stored_hash in rows:
            expected = hashlib.sha256((previous + payload).encode()).hexdigest()
            if stored_previous != previous or stored_hash != expected:
                return False, len(rows), head
            previous, head, count = stored_hash, stored_hash, count + 1
        return True, count, head

    def recent(self, limit: int = 100) -> list[EvidenceEvent]:
        limit = max(1, min(limit, 1000))
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM evidence_ledger ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
        return [EvidenceEvent.model_validate_json(row[0]) for row in rows]
