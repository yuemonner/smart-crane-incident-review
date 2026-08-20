from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from .models import EvidenceEvent, EvidenceMode, EvidenceType, IntegrityStatus


class AcecoPostgresReadOnlyConnector:
    """Bounded, read-only access to ACECO operational evidence.

    The adapter intentionally has no generic query facility and never reads the
    edge_users table. The session and every transaction are forced read-only.
    """

    def __init__(self, host, port, database, user, password):
        self.config = dict(host=host, port=port, dbname=database, user=user,
                           password=password, connect_timeout=5,
                           options="-c default_transaction_read_only=on")

    @property
    def configured(self):
        return all(self.config.get(k) for k in ("host", "dbname", "user", "password"))

    def _connect(self):
        return psycopg.connect(**self.config, row_factory=dict_row)

    def status(self):
        if not self.configured:
            return {"configured": False, "connected": False}
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database(), current_setting('transaction_read_only')")
            identity = cur.fetchone()
            cur.execute("""
                SELECT
                  (SELECT count(*) FROM (SELECT 1 FROM faults LIMIT 10001) x) AS faults,
                  (SELECT count(*) FROM (SELECT 1 FROM notifications LIMIT 10001) x) AS notifications,
                  (SELECT count(DISTINCT crane_uuid) FROM faults) AS cranes
            """)
            counts = cur.fetchone()
        return {"configured": True, "connected": True, "database": identity["current_database"],
                "user": identity["current_user"], "transaction_read_only": identity["current_setting"],
                "records": dict(counts), "included_tables": ["faults", "notifications"],
                "excluded_tables": ["edge_users"]}

    def collect(self, since: datetime | None = None, limit: int = 5000):
        since = since or datetime.now(timezone.utc) - timedelta(days=730)
        limit = max(1, min(limit, 5000))
        events = []
        retrieved_at = datetime.now(timezone.utc)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, crane_uuid, edge_uuid, motion_uuid, fault_code,
                       fault_text, duration, created_date, sync_date
                FROM faults WHERE created_date >= %s
                ORDER BY created_date DESC LIMIT %s
            """, (since, limit))
            for row in cur.fetchall():
                events.append(EvidenceEvent(
                    id=f"PG-faults-{row['id']}", type=EvidenceType.alarm,
                    occurred_at=row["created_date"], entity_id=row["crane_uuid"],
                    title=f"{row['fault_code']}: {row['fault_text']}",
                    source="ACECO edge PostgreSQL · faults",
                    source_url=f"aceco-db://api_edge/faults/{row['id']}",
                    retrieved_at=retrieved_at, evidence_mode=EvidenceMode.live,
                    integrity=IntegrityStatus(transport="PostgreSQL TLS/tunnel state not attested",
                        limitation="Read from the operational edge database; no cryptographic source signature or chain of custody was verified."),
                    attributes={"record_id": row["id"], "edge_uuid": row["edge_uuid"],
                                "motion_uuid": row["motion_uuid"], "fault_code": row["fault_code"],
                                "duration_seconds": row["duration"], "sync_date": row["sync_date"],
                                "provenance": "live read-only ACECO edge database"}))
            cur.execute("""
                SELECT id, crane_uuid, edge_uuid, motion_uuid, event_uuid,
                       event_name, event_actions, created_date, is_synchronized
                FROM notifications WHERE created_date >= %s
                ORDER BY created_date DESC LIMIT %s
            """, (since, limit))
            for row in cur.fetchall():
                events.append(EvidenceEvent(
                    id=f"PG-notifications-{row['id']}", type=EvidenceType.device_event,
                    occurred_at=row["created_date"], entity_id=row["crane_uuid"],
                    title=f"Notification: {row['event_name']}",
                    source="ACECO edge PostgreSQL · notifications",
                    source_url=f"aceco-db://api_edge/notifications/{row['id']}",
                    retrieved_at=retrieved_at, evidence_mode=EvidenceMode.live,
                    integrity=IntegrityStatus(transport="PostgreSQL TLS/tunnel state not attested",
                        limitation="Read from the operational edge database; no cryptographic source signature or chain of custody was verified."),
                    attributes={"record_id": row["id"], "edge_uuid": row["edge_uuid"],
                                "motion_uuid": row["motion_uuid"], "event_uuid": row["event_uuid"],
                                "event_actions": row["event_actions"],
                                "is_synchronized": row["is_synchronized"],
                                "patterns": ["notification_event"],
                                "provenance": "live read-only ACECO edge database"}))
        return sorted(events, key=lambda event: event.occurred_at)
