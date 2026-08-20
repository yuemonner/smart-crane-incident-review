from datetime import datetime, timezone

from app.capture import RuntimeCapture, TraceSample
from app.ledger import EvidenceLedger
from app.models import CriticalSnapshot, EvidenceMode


NOW = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)


def test_critical_snapshot_freezes_recent_trace_and_enters_hash_chain(tmp_path):
    capture = RuntimeCapture(max_samples=3)
    capture.trace(TraceSample(id="trace-1", entity_id="crane-1", occurred_at=NOW,
                              operating_mode="hoisting", state={"load": 82}))
    event = capture.critical(CriticalSnapshot(id="snap-1", entity_id="crane-1",
        occurred_at=NOW, trigger="drive fault", firmware_version="4.9",
        config_version="C17", critical_state_vector={"drive_ready": False}))
    assert event.capture_class.value == "critical_snapshot"
    assert event.attributes["ring_buffer_trace"][0]["id"] == "trace-1"
    assert event.evidence_mode == EvidenceMode.live

    ledger = EvidenceLedger(str(tmp_path / "ledger.sqlite3"))
    assert ledger.append(event)["added"] is True
    assert ledger.append(event)["added"] is False
    status = ledger.status()
    assert status["entries"] == 1 and status["chain_valid"] is True
    assert "not established" in status["limitation"]


def test_ring_buffer_keeps_only_reconstructability_window():
    capture = RuntimeCapture(max_samples=2)
    for index in range(3):
        capture.trace(TraceSample(id=f"trace-{index}", entity_id="crane-1",
                                  occurred_at=NOW, state={"index": index}))
    assert [sample.id for sample in capture.traces] == ["trace-1", "trace-2"]
