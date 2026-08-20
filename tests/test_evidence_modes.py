from datetime import datetime, timezone

from app.memory import IncidentMemory
from app.models import (EvidenceEvent, EvidenceMode, EvidenceType, IncidentRecord,
                        IncidentRequest, KnowledgeSnapshot)
from app.service import EvidenceService


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def test_evidence_modes_are_never_mixed():
    events = [
        EvidenceEvent(id="demo", type=EvidenceType.alarm, occurred_at=NOW,
                      entity_id="crane", title="synthetic", source="fixture"),
        EvidenceEvent(id="live", type=EvidenceType.alarm, occurred_at=NOW,
                      entity_id="crane", title="observed", source="db",
                      evidence_mode=EvidenceMode.live, retrieved_at=NOW),
    ]
    result = EvidenceService(events).investigate(IncidentRequest(
        entity_id="crane", incident_time=NOW, evidence_mode=EvidenceMode.live))
    assert [event.id for event in result.timeline] == ["live"]
    assert result.evidence_mode == EvidenceMode.live


def test_incident_memory_is_durable(tmp_path):
    path = tmp_path / "incidents.sqlite3"
    record = IncidentRecord(id="I-1", entity_id="crane", title="Alarm",
                            incident_time=NOW, owner="Engineer", decision="Rollback",
                            outcome="Connectivity restored", knowledge_at_decision=KnowledgeSnapshot(
                                captured_at=NOW, observed=["Device disconnected"],
                                assumptions=["Deployment may be related"],
                                unknowns=["Device-specific or deployment-wide"],
                                evidence_ids=["alarm-1"]))
    IncidentMemory(str(path)).put(record)
    loaded = IncidentMemory(str(path)).get("I-1")
    assert loaded and loaded.owner == "Engineer" and loaded.decision == "Rollback"
    assert loaded.outcome == "Connectivity restored"
    assert loaded.knowledge_at_decision.observed == ["Device disconnected"]
