import re
from datetime import datetime, timezone
from pathlib import Path

from .models import EvidenceEvent, EvidenceType

TIMESTAMP = re.compile(r"(?P<ts>20\d\d-\d\d-\d\d[ T]\d\d:\d\d:\d\d)")
DEVICE = re.compile(r"\b(?:device|ubuntu@)[^\w]*(?P<id>[a-f0-9]{12}|[a-f0-9-]{36})\b", re.I)
SECRET = re.compile(r"(?i)(password|passwd|token|secret|authorization|bearer|connection string)")
SIGNALS = {
    "redis_connection_refused": re.compile(r"Redis.*(?:Connection refused|Error 111)|connecting to smart_crane-edge-redis", re.I),
    "redis_timeout": re.compile(r"Timeout connecting to server|Redis.*timeout", re.I),
    "module_taskgroup_failure": re.compile(r"Unhandled exception|TaskGroup", re.I),
    "iot_duplicate_connection": re.compile(r"MultipleConnectionsException|Multiple connections detected", re.I),
    "iot_reconnect": re.compile(r"ClientAuthenticated|Unexpected disconnection|reconnect", re.I),
    "config_reload": re.compile(r"Loading current configuration|Starting tasks with configuration version", re.I),
    "e_stop": re.compile(r"\bE-?Stop\b|Emergency Stop", re.I),
    "cassandra_failure": re.compile(r"Cassandra.*(?:hang|unstable|down|Segmentation Fault|dropping connections)", re.I),
}


class LocalSmartCraneEvidenceConnector:
    """Read-only parser for local Smart Crane engineering notes and bounded log captures."""
    def __init__(self, root: str):
        self.root = Path(root)

    def status(self) -> dict:
        files = self._files()
        return {"connected": self.root.is_dir(), "root": str(self.root), "documents_visible": len(files),
                "supported": [".md", ".txt", ".vtt"]}

    def _files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(
            p for p in self.root.iterdir()
            if p.is_file()
            and p.suffix.lower() in {".md", ".txt", ".vtt"}
            and any(x in p.name.lower() for x in
                    ("smart_crane", "crane", "redis", "e-stop", "edge", "onboarding", "walkthrough"))
        )

    def collect(self) -> list[EvidenceEvent]:
        events: list[EvidenceEvent] = []
        for path in self._files():
            if "connection" in path.name.lower():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            default_entity = (DEVICE.search(text).group("id") if DEVICE.search(text) else None)
            for line_no, line in enumerate(text.splitlines(), 1):
                if SECRET.search(line) or not (match := TIMESTAMP.search(line)):
                    continue
                patterns = [name for name, regex in SIGNALS.items() if regex.search(line)]
                if not patterns:
                    continue
                occurred = datetime.fromisoformat(match.group("ts")).replace(tzinfo=timezone.utc)
                entity_match = DEVICE.search(line)
                entity = entity_match.group("id") if entity_match else default_entity
                safe_line = re.sub(r"\s+", " ", line).strip()[:280]
                event_type = EvidenceType.alarm if any(x in patterns for x in ("e_stop", "iot_duplicate_connection")) else EvidenceType.device_event
                events.append(EvidenceEvent(
                    id=f"LOCAL-{path.stem[:35]}-{line_no}", type=event_type, occurred_at=occurred,
                    entity_id=entity, title=safe_line, source=f"Local evidence · {path.name}",
                    attributes={"patterns": patterns, "path": str(path), "line": line_no,
                                "provenance": "user-authored local engineering evidence"},
                ))
        return events
