from collections import deque
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .models import (AssertionKind, CaptureClass, CriticalSnapshot, EvidenceEvent,
                     EvidenceMode, EvidenceType, IntegrityStatus)


class TraceSample(BaseModel):
    id: str
    entity_id: str
    occurred_at: datetime
    component_id: str | None = None
    operating_mode: str | None = None
    state: dict = Field(default_factory=dict)


class RuntimeCapture:
    """Lightweight ring buffer; continuous telemetry remains in its source system."""

    def __init__(self, max_samples: int = 500):
        self.traces = deque(maxlen=max_samples)

    def trace(self, sample: TraceSample):
        self.traces.append(sample)
        return {"buffered": True, "buffer_size": len(self.traces), "capacity": self.traces.maxlen}

    def critical(self, snapshot: CriticalSnapshot) -> EvidenceEvent:
        related = set(snapshot.related_ids)
        recent = [item.model_dump(mode="json") for item in self.traces
                  if item.entity_id == snapshot.entity_id and item.id not in related][-50:]
        return EvidenceEvent(id=snapshot.id, type=EvidenceType.snapshot,
            occurred_at=snapshot.occurred_at, entity_id=snapshot.entity_id,
            title=f"Critical snapshot: {snapshot.trigger}", source="Runtime capture",
            retrieved_at=datetime.now(timezone.utc), evidence_mode=EvidenceMode.live,
            capture_class=CaptureClass.critical_snapshot, assertion_kind=AssertionKind.observed,
            integrity=IntegrityStatus(transport="local runtime capture",
                limitation="Application snapshot; atomicity depends on the emitting integration and clocks are not independently attested."),
            attributes={**snapshot.model_dump(mode="json"), "ring_buffer_trace": recent})

    def status(self):
        return {"strategy": "reconstructability_over_completeness",
                "buffer_size": len(self.traces), "capacity": self.traces.maxlen,
                "continuous_telemetry_owner": "source system",
                "critical_snapshot_owner": "local evidence ledger"}
