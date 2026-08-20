from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    commit = "commit"
    pull_request = "pull_request"
    build = "build"
    deployment = "deployment"
    test = "test"
    config_change = "config_change"
    device_event = "device_event"
    alarm = "alarm"
    work_item = "work_item"
    snapshot = "snapshot"
    intervention = "intervention"


class CaptureClass(str, Enum):
    source_reference = "source_reference"
    operational_trace = "operational_trace"
    critical_snapshot = "critical_snapshot"
    audit_event = "audit_event"


class AssertionKind(str, Enum):
    observed = "observed"
    inferred = "inferred"
    human_asserted = "human_asserted"


class ClaimState(str, Enum):
    observed = "observed"
    evidence_supported = "evidence_supported"
    assumption = "assumption"
    superseded = "superseded"


class EvidenceMode(str, Enum):
    demo = "demo"
    cached = "cached"
    partial = "partial"
    live = "live"


class IntegrityStatus(BaseModel):
    transport: str = "not_recorded"
    content_hash: str | None = None
    limitation: str = "Source record was normalized after retrieval; chain of custody is not established."


class EvidenceEvent(BaseModel):
    id: str
    type: EvidenceType
    occurred_at: datetime
    entity_id: str | None = None
    title: str
    source: str
    source_url: str | None = None
    retrieved_at: datetime | None = None
    evidence_mode: EvidenceMode = EvidenceMode.demo
    integrity: IntegrityStatus = Field(default_factory=IntegrityStatus)
    capture_class: CaptureClass = CaptureClass.source_reference
    assertion_kind: AssertionKind = AssertionKind.observed
    confidence: float | None = Field(default=None, ge=0, le=1)
    supersedes_evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSnapshot(BaseModel):
    captured_at: datetime
    observed: list[str] = Field(default_factory=list)
    evidence_supported: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitation: str = "This records the information available at the time; later evidence does not rewrite it."


class CriticalSnapshot(BaseModel):
    id: str
    entity_id: str
    occurred_at: datetime
    trigger: str
    software_version: str | None = None
    firmware_version: str | None = None
    config_version: str | None = None
    operating_mode: str | None = None
    critical_state_vector: dict[str, Any] = Field(default_factory=dict)
    state_diff: dict[str, Any] = Field(default_factory=dict)
    recent_actions: list[dict[str, Any]] = Field(default_factory=list)
    related_ids: list[str] = Field(default_factory=list)
    intervention_context: dict[str, Any] = Field(default_factory=dict)


class IncidentRequest(BaseModel):
    entity_id: str
    incident_time: datetime
    window_hours: int = Field(default=72, ge=1, le=720)
    evidence_mode: EvidenceMode | None = None


class KnowledgeStatus(BaseModel):
    confirmed: list[str]
    not_established: list[str]
    evidence_gaps: list[str]


class LastKnownGoodState(BaseModel):
    established: bool = False
    observed_at: datetime | None = None
    software_revision: str | None = None
    config_profile: str | None = None
    runtime_state: str | None = None
    test_evidence: list[str] = Field(default_factory=list)
    validated_by: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    limitation: str = "No explicit validation marker establishes a last known good state."


class ScopeAssessment(BaseModel):
    classification: str = "not_established"
    device_evidence_count: int = 0
    peer_signal_count: int = 0
    peer_incident_count: int = 0
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


class Investigation(BaseModel):
    entity_id: str
    incident_time: datetime
    timeline: list[EvidenceEvent]
    what_changed: list[EvidenceEvent]
    status: KnowledgeStatus
    evidence_mode: EvidenceMode = EvidenceMode.demo
    freshest_source_at: datetime | None = None
    stalest_source_at: datetime | None = None
    coordination: dict[str, Any] = Field(default_factory=dict)
    last_known_good: LastKnownGoodState = Field(default_factory=LastKnownGoodState)
    scope_assessment: ScopeAssessment = Field(default_factory=lambda: ScopeAssessment(
        explanation="There is not enough comparison evidence to distinguish a device-specific issue from a deployment-wide issue."))


class IncidentSummary(BaseModel):
    id: str
    entity_id: str
    title: str
    incident_time: datetime
    evidence_mode: EvidenceMode
    source: str


class IncidentRecord(BaseModel):
    id: str
    entity_id: str
    title: str
    incident_time: datetime
    status: str = "open"
    owner: str | None = None
    checkpoint_at: datetime | None = None
    decision: str | None = None
    decision_by: str | None = None
    decision_at: datetime | None = None
    notes: str | None = None
    outcome: str | None = None
    outcome_recorded_at: datetime | None = None
    knowledge_at_decision: KnowledgeSnapshot | None = None


class ExposureSignature(BaseModel):
    firmware: str | None
    config_profile: str | None
    precursor_pattern: list[str]
    derived_from_evidence_ids: list[str]


class AssetMatch(BaseModel):
    entity_id: str
    score: int
    exposure_match: bool
    precursor_detected: bool
    matched_factors: list[str]
    evidence_ids: list[str]
    customer: str


class WhereElseResult(BaseModel):
    source_entity_id: str
    signature: ExposureSignature
    exposed_count: int
    precursor_count: int
    customer_count: int
    matches: list[AssetMatch]
    status: KnowledgeStatus
