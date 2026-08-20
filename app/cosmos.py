import hashlib
import json
import ssl
from datetime import datetime, timedelta, timezone

from .models import EvidenceEvent, EvidenceMode, EvidenceType, IntegrityStatus


class CosmosTelemetryReadOnlyConnector:
    """Bounded read-only reader for the ACECO Cosmos Cassandra telemetry table."""

    def __init__(self, host, port, username, password, keyspace="cloud_core"):
        self.host, self.port, self.username, self.password = host, port, username, password
        self.keyspace = keyspace

    @property
    def configured(self):
        return all((self.host, self.port, self.username, self.password, self.keyspace))

    def _session(self):
        from cassandra.auth import PlainTextAuthProvider
        from cassandra.cluster import Cluster
        context = ssl.create_default_context()
        cluster = Cluster([self.host], port=self.port,
            auth_provider=PlainTextAuthProvider(username=self.username, password=self.password),
            ssl_context=context, protocol_version=4)
        return cluster, cluster.connect(self.keyspace)

    def status(self):
        if not self.configured:
            return {"configured": False, "connected": False}
        cluster, session = self._session()
        try:
            row = session.execute("SELECT release_version FROM system.local").one()
            return {"configured": True, "connected": True, "keyspace": self.keyspace,
                    "table": "crane_telemetry", "mode": "bounded SELECT-only",
                    "server_version": getattr(row, "release_version", None)}
        finally:
            cluster.shutdown()

    def collect(self, edge_uuid: str, incident_time: datetime, window_hours: int = 72,
                limit: int = 5000) -> list[EvidenceEvent]:
        if not self.configured:
            raise RuntimeError("Cosmos Cassandra is not configured")
        start = incident_time - timedelta(hours=max(1, min(window_hours, 720)))
        end = incident_time + timedelta(hours=1)
        limit = max(1, min(limit, 5000))
        cluster, session = self._session()
        retrieved_at = datetime.now(timezone.utc)
        try:
            query = """SELECT edge_uuid, motion_uuid, query_timestamp, last_activity_timestamp,
                       load_timestamp, total_motors, vfd_status, motion_data
                       FROM crane_telemetry WHERE edge_uuid=%s AND query_timestamp >= %s
                       AND query_timestamp <= %s LIMIT %s ALLOW FILTERING"""
            rows = session.execute(query, (edge_uuid, start, end, limit))
            events = []
            for index, row in enumerate(rows):
                raw = row.motion_data
                motion = json.loads(raw) if isinstance(raw, str) else (raw or {})
                signal = self._signal(motion)
                digest = hashlib.sha256(json.dumps({"edge_uuid": row.edge_uuid,
                    "motion_uuid": row.motion_uuid, "query_timestamp": str(row.query_timestamp),
                    "motion_data": motion}, sort_keys=True, default=str).encode()).hexdigest()
                events.append(EvidenceEvent(id=f"COSMOS-{row.edge_uuid}-{row.motion_uuid}-{index}-{digest[:10]}",
                    type=EvidenceType.alarm if signal["alarm"] else EvidenceType.device_event,
                    occurred_at=row.query_timestamp, entity_id=row.edge_uuid,
                    title=signal["title"], source="ACECO Cosmos Cassandra · crane_telemetry",
                    source_url=None, retrieved_at=retrieved_at, evidence_mode=EvidenceMode.live,
                    integrity=IntegrityStatus(transport="TLS", content_hash=digest,
                        limitation="Hash covers the normalized row at retrieval time; it does not prove source immutability, clock accuracy, calibration, or legal chain of custody."),
                    attributes={"motion_uuid": row.motion_uuid, "last_activity_timestamp": row.last_activity_timestamp,
                        "load_timestamp": row.load_timestamp, "total_motors": row.total_motors,
                        "vfd_status": row.vfd_status, "physical_signal": True, **signal, "motion_data": motion}))
            return sorted(events, key=lambda e: e.occurred_at)
        finally:
            cluster.shutdown()

    @staticmethod
    def _signal(motion):
        faults = motion.get("drive_fault_list") or []
        alarm = bool(motion.get("drive_alarm") or motion.get("drive_fault") or faults)
        load = motion.get("crane_weight", motion.get("loadcell"))
        temp = motion.get("heatsink_temperature")
        title = "Drive fault/alarm telemetry" if alarm else "Crane motion telemetry sample"
        patterns = []
        if alarm:
            patterns.append("drive_fault_or_alarm")
        return {"title": title, "alarm": alarm, "patterns": patterns,
                "load": load, "heatsink_temperature": temp,
                "current": motion.get("current"), "torque": motion.get("torque"),
                "output_hz": motion.get("output_hz"), "drive_ready": motion.get("drive_ready"),
                "faults": faults}
