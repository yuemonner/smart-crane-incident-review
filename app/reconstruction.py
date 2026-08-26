from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AssertionType(str, Enum):
    observed = "observed"
    inferred = "inferred"
    human_asserted = "human_asserted"


class CoverageState(str, Enum):
    complete = "COMPLETE"
    partial = "PARTIAL"
    missing = "MISSING"


class CanonicalEvidence(BaseModel):
    id: str
    asset_id: str | None = None
    source_system: str
    source_record_id: str
    event_time: datetime
    observed_at: datetime
    ingested_at: datetime
    event_type: str
    subject: str
    before: str | None = None
    after: str | None = None
    assertion_type: AssertionType = AssertionType.observed
    confidence: float = Field(default=1.0, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)


class StateField(BaseModel):
    value: str | None = None
    state: CoverageState
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str


class TemporalState(BaseModel):
    asset_id: str
    state_time: datetime
    knowledge_time: datetime
    fields: dict[str, StateField]
    ignored_late_evidence_ids: list[str] = Field(default_factory=list)


class ChangeRecord(BaseModel):
    subject: str
    before: str | None
    after: str | None
    event_time: datetime
    source_system: str
    evidence_id: str
    evidence_strength: AssertionType


class ReconstructabilityItem(BaseModel):
    field: str
    state: CoverageState
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


class ReconstructabilityReport(BaseModel):
    asset_id: str
    decision_time: datetime
    coverage: list[ReconstructabilityItem]
    minimum_future_capture: list[str]


class PeerMatch(BaseModel):
    asset_id: str
    exposed: bool
    precursor_detected: bool
    matching_failure: bool
    evidence_ids: list[str]


class PeerContextResult(BaseModel):
    signature: dict[str, str | None]
    exposed_count: int
    precursor_count: int
    matching_failure_count: int
    counterexample_count: int
    matches: list[PeerMatch]


class ContextSignature(BaseModel):
    id: str
    firmware: str | None
    configuration: str | None
    precursor_signal: str | None
    alarm: str | None
    missing_fields: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class InterventionRecord(BaseModel):
    id: str
    actor: str | None
    action: str
    reason: str | None
    recorded_at: datetime
    evidence_ids: list[str] = Field(default_factory=list)


class OutcomeRecord(BaseModel):
    id: str
    recorded_at: datetime
    result: str
    recurrence: bool
    time_to_resolution_hours: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class OperationalEpisode(BaseModel):
    id: str
    asset_id: str
    decision_time: datetime
    decision: str
    context_signature: ContextSignature
    machine_state: TemporalState
    knowledge_state: dict[str, list[str]]
    interventions: list[InterventionRecord]
    outcome: OutcomeRecord | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class SimilarEpisode(BaseModel):
    episode_id: str
    asset_id: str
    similarity_score: int
    previous_action: str
    outcome: str
    recurrence: bool
    caveat: str


class HistoricalOutcomeSummary(BaseModel):
    previous_action: str
    cases: int
    outcome: str


class LearningReport(BaseModel):
    target_episode_id: str
    context_signature: ContextSignature
    similar_contexts: int
    similar_episodes: list[SimilarEpisode]
    outcomes: list[HistoricalOutcomeSummary]
    evidence_to_capture_next: list[str]
    limitation: str = "Historical outcomes are retrieval context, not a recommendation."


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    evidence_ids: list[str] = Field(default_factory=list)


class OperationalContextGraph(BaseModel):
    episode_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    limitation: str = "Graph relations preserve sequence, association and review basis. They do not establish causality."


STATE_SUBJECTS = {
    "firmware": ("software", "Software or firmware version at the review time."),
    "config": ("configuration", "Configuration profile at the review time."),
    "test": ("last_test", "Most recent validation or test result before the review time."),
    "last_known_good": ("last_known_good", "Explicit validated state marker before the review time."),
    "alarm": ("recent_alarms", "Recent alarm evidence in the lookback window."),
    "intervention": ("recent_interventions", "Recent intervention evidence in the lookback window."),
}


class ReconstructionEngine:
    def __init__(self, evidence: list[CanonicalEvidence]):
        self.evidence = sorted(evidence, key=lambda e: (e.event_time, e.ingested_at, e.id))

    def state_at(
        self,
        asset_id: str,
        state_time: datetime,
        knowledge_time: datetime | None = None,
        lookback: timedelta = timedelta(hours=72),
    ) -> TemporalState:
        knowledge_time = knowledge_time or state_time
        known = [
            e for e in self.evidence
            if e.asset_id in (asset_id, None)
            and e.event_time <= state_time
            and e.ingested_at <= knowledge_time
        ]
        late = [
            e.id for e in self.evidence
            if e.asset_id in (asset_id, None)
            and e.event_time <= state_time
            and e.ingested_at > knowledge_time
        ]
        fields: dict[str, StateField] = {}
        for subject, (field_name, explanation) in STATE_SUBJECTS.items():
            if subject in {"alarm", "intervention"}:
                events = [
                    e for e in known
                    if e.subject == subject and state_time - lookback <= e.event_time <= state_time
                ]
                fields[field_name] = StateField(
                    value=str(len(events)) if events else None,
                    state=CoverageState.complete if events else CoverageState.missing,
                    evidence_ids=[e.id for e in events],
                    explanation=explanation if events else f"No {subject} evidence in lookback window.",
                )
                continue
            event = max((e for e in known if e.subject == subject), key=lambda e: e.event_time, default=None)
            fields[field_name] = StateField(
                value=event.after if event else None,
                state=CoverageState.complete if event else CoverageState.missing,
                evidence_ids=[event.id] if event else [],
                explanation=explanation if event else f"No {subject} evidence known by this knowledge time.",
            )
        return TemporalState(
            asset_id=asset_id,
            state_time=state_time,
            knowledge_time=knowledge_time,
            fields=fields,
            ignored_late_evidence_ids=late,
        )

    def detect_changes(
        self,
        asset_id: str,
        incident_time: datetime,
        lookback: timedelta = timedelta(hours=72),
    ) -> list[ChangeRecord]:
        start = incident_time - lookback
        changes = [
            e for e in self.evidence
            if e.asset_id in (asset_id, None)
            and start <= e.event_time <= incident_time
            and (e.before is not None or e.after is not None)
        ]
        return [
            ChangeRecord(
                subject=e.subject,
                before=e.before,
                after=e.after,
                event_time=e.event_time,
                source_system=e.source_system,
                evidence_id=e.id,
                evidence_strength=e.assertion_type,
            )
            for e in changes
        ]

    def analyze_reconstructability(
        self,
        asset_id: str,
        decision_time: datetime,
        knowledge_time: datetime | None = None,
    ) -> ReconstructabilityReport:
        state = self.state_at(asset_id, decision_time, knowledge_time)
        coverage: list[ReconstructabilityItem] = []

        def item(field: str, status: CoverageState, explanation: str, evidence_ids: list[str] | None = None):
            coverage.append(ReconstructabilityItem(
                field=field, state=status, explanation=explanation, evidence_ids=evidence_ids or []
            ))

        item("Software version", state.fields["software"].state, state.fields["software"].explanation, state.fields["software"].evidence_ids)
        item("Configuration", state.fields["configuration"].state, state.fields["configuration"].explanation, state.fields["configuration"].evidence_ids)
        item("Telemetry before event", CoverageState.complete, "Recent telemetry trace exists for the review window.", self._ids(asset_id, "telemetry", decision_time))
        item("Pre-event machine state", CoverageState.partial, "Telemetry exists, but local controller state snapshot is not retained.", self._ids(asset_id, "telemetry", decision_time))
        item("Operator action", CoverageState.missing, "No append-only intervention record with actor and reason was found.")
        item("Reason for intervention", CoverageState.missing, "Human explanation was not captured as structured evidence.")
        item("Outcome", CoverageState.partial, "Later operating outcome exists only if a follow-up record is attached.", self._ids(asset_id, "outcome", decision_time + timedelta(hours=8)))

        future_capture = [
            "retain 5-minute local runtime trace around critical triggers",
            "snapshot controller state on E-stop or connectivity loss",
            "record manual override with actor, reason, start time and end time",
            "preserve exact configuration diff for activated profile",
            "attach outcome follow-up to the original decision record",
        ]
        return ReconstructabilityReport(
            asset_id=asset_id,
            decision_time=decision_time,
            coverage=coverage,
            minimum_future_capture=future_capture,
        )

    def match_peers(
        self,
        asset_id: str,
        incident_time: datetime,
        precursor_subject: str = "telemetry",
    ) -> PeerContextResult:
        state = self.state_at(asset_id, incident_time)
        firmware = state.fields["software"].value
        config = state.fields["configuration"].value
        assets = sorted({e.asset_id for e in self.evidence if e.asset_id and e.asset_id != asset_id})
        matches: list[PeerMatch] = []
        for peer in assets:
            peer_state = self.state_at(peer, incident_time)
            exposed = (
                peer_state.fields["software"].value == firmware
                and peer_state.fields["configuration"].value == config
            )
            precursor = any(
                e.asset_id == peer and e.subject == precursor_subject and e.event_time <= incident_time
                for e in self.evidence
            )
            failure = any(
                e.asset_id == peer and e.subject == "alarm" and e.event_time <= incident_time
                for e in self.evidence
            )
            if exposed:
                evidence_ids = []
                evidence_ids.extend(peer_state.fields["software"].evidence_ids)
                evidence_ids.extend(peer_state.fields["configuration"].evidence_ids)
                evidence_ids.extend(self._ids(peer, precursor_subject, incident_time))
                matches.append(PeerMatch(
                    asset_id=peer,
                    exposed=exposed,
                    precursor_detected=precursor,
                    matching_failure=failure,
                    evidence_ids=evidence_ids,
                ))
        return PeerContextResult(
            signature={"firmware": firmware, "config": config, "precursor_signal": precursor_subject},
            exposed_count=len(matches),
            precursor_count=sum(m.precursor_detected for m in matches),
            matching_failure_count=sum(m.matching_failure for m in matches),
            counterexample_count=sum(1 for m in matches if not m.precursor_detected),
            matches=matches,
        )

    def build_episode(
        self,
        asset_id: str,
        decision_time: datetime,
        knowledge_time: datetime | None = None,
        decision: str = "Hold deployment",
    ) -> OperationalEpisode:
        knowledge_time = knowledge_time or decision_time
        state = self.state_at(asset_id, decision_time, knowledge_time)
        known = [
            e for e in self.evidence
            if e.asset_id in (asset_id, None)
            and e.event_time <= decision_time
            and e.ingested_at <= knowledge_time
        ]
        evidence_state = _classified_evidence(known, decision_time, knowledge_time)
        signature = self.context_signature(asset_id, decision_time, knowledge_time)
        interventions = [
            InterventionRecord(
                id=e.id,
                actor=e.provenance.get("actor"),
                action=e.after or e.event_type,
                reason=e.provenance.get("reason"),
                recorded_at=e.observed_at,
                evidence_ids=[e.id],
            )
            for e in known
            if e.subject in {"intervention", "hypothesis"} or e.event_type in {"intervention", "note"}
        ]
        outcome_event = max(
            (
                e for e in self.evidence
                if e.asset_id == asset_id
                and e.subject == "outcome"
                and e.ingested_at <= knowledge_time + timedelta(days=14)
            ),
            key=lambda e: e.event_time,
            default=None,
        )
        outcome = None
        if outcome_event:
            outcome = OutcomeRecord(
                id=outcome_event.id,
                recorded_at=outcome_event.event_time,
                result=outcome_event.after or "outcome recorded",
                recurrence="recurrence" in (outcome_event.after or "").lower(),
                time_to_resolution_hours=round((outcome_event.event_time - decision_time).total_seconds() / 3600, 2),
                evidence_ids=[outcome_event.id],
            )
        return OperationalEpisode(
            id=f"episode-{asset_id}-{decision_time.strftime('%Y%m%d%H%M')}",
            asset_id=asset_id,
            decision_time=decision_time,
            decision=decision,
            context_signature=signature,
            machine_state=state,
            knowledge_state=evidence_state,
            interventions=interventions,
            outcome=outcome,
            evidence_ids=[e.id for e in known],
        )

    def context_signature(
        self,
        asset_id: str,
        decision_time: datetime,
        knowledge_time: datetime | None = None,
    ) -> ContextSignature:
        state = self.state_at(asset_id, decision_time, knowledge_time)
        firmware = state.fields["software"].value
        config = state.fields["configuration"].value
        telemetry = max(
            (
                e for e in self.evidence
                if e.asset_id == asset_id
                and e.subject == "telemetry"
                and e.event_time <= decision_time
                and e.ingested_at <= (knowledge_time or decision_time)
            ),
            key=lambda e: e.event_time,
            default=None,
        )
        alarm = max(
            (
                e for e in self.evidence
                if e.asset_id == asset_id
                and e.subject == "alarm"
                and e.event_time <= decision_time
                and e.ingested_at <= (knowledge_time or decision_time)
            ),
            key=lambda e: e.event_time,
            default=None,
        )
        missing = [
            item.field for item in self.analyze_reconstructability(asset_id, decision_time, knowledge_time).coverage
            if item.state == CoverageState.missing
        ]
        evidence_ids = []
        for field in ("software", "configuration"):
            evidence_ids.extend(state.fields[field].evidence_ids)
        if telemetry:
            evidence_ids.append(telemetry.id)
        if alarm:
            evidence_ids.append(alarm.id)
        return ContextSignature(
            id=f"sig:{firmware or 'unknown'}:{config or 'unknown'}:{telemetry.after if telemetry else 'no-telemetry'}:{alarm.after if alarm else 'no-alarm'}",
            firmware=firmware,
            configuration=config,
            precursor_signal=telemetry.after if telemetry else None,
            alarm=alarm.after if alarm else None,
            missing_fields=missing,
            evidence_ids=evidence_ids,
        )

    def learning_report(self, episode: OperationalEpisode) -> LearningReport:
        similar = _synthetic_similar_episodes(episode.context_signature)
        outcomes_by_action: dict[str, list[SimilarEpisode]] = {}
        for item in similar:
            outcomes_by_action.setdefault(item.previous_action, []).append(item)
        summaries = [
            HistoricalOutcomeSummary(
                previous_action=action,
                cases=len(items),
                outcome=_summarize_outcomes(items),
            )
            for action, items in outcomes_by_action.items()
        ]
        return LearningReport(
            target_episode_id=episode.id,
            context_signature=episode.context_signature,
            similar_contexts=len(similar),
            similar_episodes=similar,
            outcomes=summaries,
            evidence_to_capture_next=[
                "5-minute local controller trace around critical triggers",
                "manual intervention actor, reason and exact parameter delta",
                "configuration diff attached to each activated profile",
                "outcome follow-up linked to the original decision episode",
            ],
        )

    def context_graph(self, episode: OperationalEpisode) -> OperationalContextGraph:
        nodes = [
            GraphNode(id=episode.asset_id, label=episode.asset_id, type="machine"),
            GraphNode(id=episode.context_signature.id, label="Context signature", type="context_signature",
                      properties=episode.context_signature.model_dump(mode="json")),
            GraphNode(id=episode.id, label="Operational episode", type="episode"),
            GraphNode(id=f"{episode.id}:decision", label=episode.decision, type="human_decision"),
        ]
        edges = [
            GraphEdge(source=episode.asset_id, target=episode.context_signature.id,
                      relation="had_state_signature", evidence_ids=episode.context_signature.evidence_ids),
            GraphEdge(source=episode.context_signature.id, target=episode.id,
                      relation="reviewed_during", evidence_ids=episode.evidence_ids),
            GraphEdge(source=episode.id, target=f"{episode.id}:decision",
                      relation="decision_based_on", evidence_ids=episode.evidence_ids),
        ]
        for intervention in episode.interventions:
            nodes.append(GraphNode(id=intervention.id, label=intervention.action, type="intervention",
                                   properties=intervention.model_dump(mode="json")))
            edges.append(GraphEdge(source=intervention.id, target=episode.id,
                                   relation="human_context_recorded_during",
                                   evidence_ids=intervention.evidence_ids))
        if episode.outcome:
            nodes.append(GraphNode(id=episode.outcome.id, label=episode.outcome.result, type="outcome",
                                   properties=episode.outcome.model_dump(mode="json")))
            edges.append(GraphEdge(source=f"{episode.id}:decision", target=episode.outcome.id,
                                   relation="outcome_observed_after",
                                   evidence_ids=episode.outcome.evidence_ids))
        return OperationalContextGraph(episode_id=episode.id, nodes=nodes, edges=edges)

    def _ids(self, asset_id: str, subject: str, before: datetime) -> list[str]:
        return [
            e.id for e in self.evidence
            if e.asset_id == asset_id and e.subject == subject and e.event_time <= before
        ]


def synthetic_operational_world(now: datetime | None = None) -> list[CanonicalEvidence]:
    now = now or datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    base = datetime(2026, 8, 14, 16, 32, tzinfo=timezone.utc)
    records: list[CanonicalEvidence] = []

    def ev(
        id: str,
        asset: str | None,
        source: str,
        hours: float,
        event_type: str,
        subject: str,
        before: str | None = None,
        after: str | None = None,
        assertion: AssertionType = AssertionType.observed,
        ingested_offset: float = -0.1,
        confidence: float = 1.0,
        **provenance: Any,
    ):
        event_time = base + timedelta(hours=hours)
        records.append(CanonicalEvidence(
            id=id,
            asset_id=asset,
            source_system=source,
            source_record_id=id,
            event_time=event_time,
            observed_at=event_time,
            ingested_at=event_time + timedelta(hours=ingested_offset),
            event_type=event_type,
            subject=subject,
            before=before,
            after=after,
            assertion_type=assertion,
            confidence=confidence,
            provenance=provenance,
        ))

    ev("CR07-LKG-217", "crane-07", "test_plan", -60, "test", "last_known_good", after="2026-08-12T04:32Z")
    ev("CR07-FW-49", "crane-07", "deployment", -36, "deployment", "firmware", before="4.8", after="4.9")
    ev("CR07-CFG-C17", "crane-07", "configuration", -35.5, "config_change", "config", before="C16", after="C17")
    ev("CR07-TEST-PASS", "crane-07", "test_plan", -34, "test", "test", after="passed")
    ev("CR07-TEL-PRE", "crane-07", "telemetry", -0.2, "device_event", "telemetry", after="email_text_alert_delivery_latency_high")
    ev("CR07-HUMAN-NETWORK", "crane-07", "operator_note", -0.03, "note", "hypothesis", after="network looked unstable", assertion=AssertionType.human_asserted)
    ev("CR07-ALARM-ESTOP", "crane-07", "telemetry", 0, "alarm", "alarm", after="E_STOP")
    ev("CR07-COUNTER-NETWORK", "crane-07", "telemetry", -0.04, "device_event", "network", after="normal", ingested_offset=2.5)
    ev("CR07-OUTCOME", "crane-07", "service_review", 4, "outcome", "outcome", after="no recurrence after limited test")

    for i in range(8, 57):
        asset = f"crane-{i:02d}"
        firmware = "4.9" if i <= 34 else "4.8"
        config = "C17" if i <= 34 else "C16"
        ev(f"{asset}-FW", asset, "deployment", -40 + i / 100, "deployment", "firmware", after=firmware)
        ev(f"{asset}-CFG", asset, "configuration", -39 + i / 100, "config_change", "config", after=config)
        if 8 <= i <= 18:
            ev(f"{asset}-PRE", asset, "telemetry", -1 + i / 100, "device_event", "telemetry", after="email_text_alert_delivery_latency_high")
        if i == 20:
            ev(f"{asset}-HUMAN-CONFLICT", asset, "operator_note", -0.5, "note", "hypothesis", after="network looked unstable", assertion=AssertionType.human_asserted)
            ev(f"{asset}-NETWORK-NORMAL", asset, "telemetry", -0.45, "device_event", "network", after="normal", ingested_offset=3)
    return records


def demo_reconstruction_report() -> dict[str, Any]:
    world = synthetic_operational_world()
    engine = ReconstructionEngine(world)
    decision_time = datetime(2026, 8, 14, 16, 32, tzinfo=timezone.utc)
    knowledge_time = datetime(2026, 8, 14, 17, 5, tzinfo=timezone.utc)
    return {
        "state_at_decision": engine.state_at("crane-07", decision_time, knowledge_time).model_dump(mode="json"),
        "current_state": engine.state_at("crane-07", decision_time, decision_time + timedelta(hours=6)).model_dump(mode="json"),
        "changes": [c.model_dump(mode="json") for c in engine.detect_changes("crane-07", decision_time)],
        "reconstructability": engine.analyze_reconstructability("crane-07", decision_time, knowledge_time).model_dump(mode="json"),
        "peer_context": engine.match_peers("crane-07", decision_time).model_dump(mode="json"),
    }


def demo_learning_report() -> dict[str, Any]:
    world = synthetic_operational_world()
    engine = ReconstructionEngine(world)
    decision_time = datetime(2026, 8, 14, 16, 32, tzinfo=timezone.utc)
    knowledge_time = datetime(2026, 8, 14, 17, 5, tzinfo=timezone.utc)
    episode = engine.build_episode("crane-07", decision_time, knowledge_time)
    learning = engine.learning_report(episode)
    graph = engine.context_graph(episode)
    return {
        "episode": episode.model_dump(mode="json"),
        "learning": learning.model_dump(mode="json"),
        "graph": graph.model_dump(mode="json"),
    }


LIVE_REVIEW_DECISION_TIME = datetime(2026, 8, 14, 17, 5, tzinfo=timezone.utc)


def live_reconstruction_report(step: int = 0) -> dict[str, Any]:
    """A deterministic event -> reconstruction -> reasoning -> decision demo.

    The dataset is representative synthetic evidence based on connected
    industrial-equipment workflows. It preserves the structure of deployment,
    configuration, telemetry, human notes, tests, peer exposure and late
    counterevidence without exposing proprietary customer records.
    """
    world = synthetic_operational_world()
    incident_time = datetime(2026, 8, 14, 16, 32, tzinfo=timezone.utc)
    stream = _live_review_stream()
    max_step = len(stream) - 1
    step = max(0, min(step, max_step))
    knowledge_time = stream[step]["knowledge_time"]
    visible = [e for e in world if e.ingested_at <= knowledge_time]
    engine = ReconstructionEngine(visible)
    state_at_review = engine.state_at("crane-07", incident_time, knowledge_time)
    current_state = ReconstructionEngine(world).state_at("crane-07", incident_time, incident_time + timedelta(hours=8))
    changes = engine.detect_changes("crane-07", incident_time)
    reconstructability = engine.analyze_reconstructability("crane-07", incident_time, knowledge_time)
    peers = engine.match_peers("crane-07", incident_time)
    where_else = peers.model_dump(mode="json")
    if step >= 11:
        where_else["matching_failure_count"] = 1
        where_else["matches"] = [
            {**match, "matching_failure": True}
            if match["asset_id"] == "crane-08" else match
            for match in where_else["matches"]
        ]
    evidence_state = _classified_evidence(visible, incident_time, knowledge_time)
    interpretation = _bounded_interpretation(evidence_state, where_else)
    frozen_decision = _frozen_decision(visible, incident_time, knowledge_time) if step >= 9 else None
    episode = engine.build_episode("crane-07", incident_time, knowledge_time) if step >= 9 else None
    learning = _historical_learning_from_report(engine.learning_report(episode)) if step >= 12 and episode else _historical_learning_pending()
    new_evidence_notice = None
    if step == 10:
        new_evidence_notice = {
            "title": "New evidence changed the current conclusion",
            "message": "Late network telemetry shows cellular state was normal near the alert window. The current interpretation changes, but the 17:05 decision context remains frozen.",
            "current_conclusion": "Network-instability explanation is less supported than it appeared at the decision time.",
            "historical_context": "Decision at 17:05 was made before CR07-COUNTER-NETWORK was available.",
        }
    if step >= 11:
        new_evidence_notice = {
            "title": "New peer alert-delivery issue changed the current conclusion",
            "message": "Crane-08 now reports the same alert-delivery issue under the same monitoring firmware / alert config exposure. Fleet-level concern is stronger, but the 17:05 decision context remains frozen.",
            "current_conclusion": "Shared alert-delivery issue is now more supported and requires peer inspection.",
            "historical_context": "Decision at 17:05 was made before the Crane-08 alert-delivery issue was available.",
        }
    return {
        "step": step,
        "max_step": max_step,
        "scenario": "representative_smart_crane_review",
        "data_boundary": "Representative synthetic evidence derived from real connected-industrial-equipment workflows. No proprietary customer records, IDs, logs or source data are included.",
        "knowledge_time": knowledge_time.isoformat(),
        "active_event": stream[step],
        "event_stream": stream[:step + 1],
        "machine_change_detected": {
            "asset_id": "crane-07",
            "firmware": "monitoring device firmware 4.8 -> 4.9",
            "configuration": "alert routing config C16 -> C17",
            "operator_context": "technician suspected network instability",
            "telemetry": "email/text alert delivery latency increased before the E-stop trigger",
        },
        "new_review": {
            "created": step >= 3,
            "title": "Crane-07 machine decision review",
            "question": "Did the E-stop email/text alert delivery path behave as expected?",
            "status": _review_status(evidence_state, reconstructability),
        },
        "reconstruct_what_changed": [c.model_dump(mode="json") for c in changes],
        "state_at_decision": state_at_review.model_dump(mode="json"),
        "current_state": current_state.model_dump(mode="json"),
        "evidence_state": evidence_state,
        "ai_reasoning_layer": interpretation,
        "where_else": where_else,
        "reconstructability": reconstructability.model_dump(mode="json"),
        "team_decision": {
            "options": ["Continue investigation", "Hold deployment", "Roll back", "Inspect peer assets", "Return to service"],
            "recorded": frozen_decision,
        },
        "new_evidence_notice": new_evidence_notice,
        "historical_learning": learning,
    }


def _live_review_stream() -> list[dict[str, Any]]:
    base = datetime(2026, 8, 14, 16, 32, tzinfo=timezone.utc)
    rows = [
        (-36.2, "deployment", "Monitoring device firmware 4.9 deployed", "ADO pipeline + deployment manifest", "Monitoring software changed 36h before the alert-delivery review trigger."),
        (-35.7, "configuration", "Alert routing config C17 activated", "Config audit", "Alert routing config changed 35.5h before the alert-delivery review trigger."),
        (-34.2, "validation", "Email/text alert delivery tests passed; high-load latency test missing", "Azure Test Plans", "Validation exists, but one important stress case is absent."),
        (-3.0, "telemetry", "Elevated email/text alert delivery latency", "Notehub + IoT Hub", "First matching telemetry signal appears before the missed acknowledgement."),
        (-0.05, "telemetry", "Alert acknowledgement missing", "IoT Hub", "Runtime signal matches the earlier alert-delivery latency pattern."),
        (-0.01, "capture", "High-resolution event window captured", "Edge capture", "3-minute machine-state window preserves the local context around the trigger."),
        (0, "alarm", "E-stop event with alert-delivery behavior under review", "IoT Hub", "Critical trigger freezes a machine decision review context."),
        (0.03, "human_context", "Technician suspected network instability", "Service note", "Human assertion is preserved separately from observed evidence."),
        (0.55, "fleet_compare", "Peer comparison completed", "reconstruction engine", "27 peers share monitoring firmware / alert config exposure; 11 show the precursor signal."),
        (0.55, "decision", "Team decision recorded: hold deployment", "Review workspace", "Decision context is frozen with evidence available at 17:05."),
        (2.5, "late_counterevidence", "Network telemetry arrived late: normal state near alert window", "Notehub + IoT Hub delayed retrieval", "Current conclusion updates without rewriting the 17:05 decision."),
        (3.2, "peer_failure", "Crane-08 reports the same alert-delivery issue", "IoT Hub + service review", "Matching alert-delivery issues update from 0 to 1 after the earlier decision."),
        (4.0, "outcome", "Historical outcome comparison generated", "operational memory", "Similar reviewed contexts become reusable learning for the next decision."),
    ]
    return [
        {
            "index": idx,
            "event_time": (base + timedelta(hours=offset)).isoformat(),
            "knowledge_time": (base + timedelta(hours=max(offset, 0) + idx * 0.02)).replace(tzinfo=timezone.utc),
            "type": kind,
            "title": title,
            "source": source,
            "reconstruction_note": note,
        }
        for idx, (offset, kind, title, source, note) in enumerate(rows)
    ]


def _classified_evidence(records: list[CanonicalEvidence], incident_time: datetime, knowledge_time: datetime) -> dict[str, list[str]]:
    ids = {e.id for e in records}
    observed = []
    human_asserted = []
    inferred = []
    not_established = [
        "monitoring firmware 4.9 caused the crane E-stop",
        "the same alert-delivery issue will affect every exposed crane",
        "operator override parameters were fully captured",
    ]
    if "CR07-FW-49" in ids:
        observed.append("monitoring device firmware 4.9 deployed")
    if "CR07-CFG-C17" in ids:
        observed.append("alert routing config C17 activated")
    if "CR07-TEL-PRE" in ids:
        observed.append("email/text alert delivery latency increased")
    if "CR07-ALARM-ESTOP" in ids:
        observed.append("E-stop occurred; alert delivery under review")
    if "CR07-COUNTER-NETWORK" in ids:
        observed.append("late telemetry: network state was normal near alert window")
    if "CR07-HUMAN-NETWORK" in ids:
        human_asserted.append("technician suspected network instability")
    if {"CR07-FW-49", "CR07-CFG-C17", "CR07-TEL-PRE"} <= ids:
        inferred.append("monitoring firmware / alert config change may be related to alert-delivery behavior")
    counterevidence = []
    if "CR07-COUNTER-NETWORK" in ids:
        counterevidence.append("network-instability hypothesis is contradicted by late telemetry")
    return {
        "observed": observed,
        "human_asserted": human_asserted,
        "inferred": inferred,
        "not_established": not_established,
        "counterevidence": counterevidence,
        "knowledge_boundary": [f"Evidence is limited to records ingested by {knowledge_time.isoformat()}"],
    }


def _bounded_interpretation(evidence_state: dict[str, list[str]], peers: PeerContextResult | dict[str, Any]) -> dict[str, Any]:
    exposed_count = peers.exposed_count if isinstance(peers, PeerContextResult) else peers["exposed_count"]
    precursor_count = peers.precursor_count if isinstance(peers, PeerContextResult) else peers["precursor_count"]
    counterexample_count = peers.counterexample_count if isinstance(peers, PeerContextResult) else peers["counterexample_count"]
    matching_failure_count = peers.matching_failure_count if isinstance(peers, PeerContextResult) else peers["matching_failure_count"]
    has_late_counter = bool(evidence_state["counterevidence"])
    if matching_failure_count:
        plausible = "more supported and requires peer inspection"
    elif has_late_counter:
        plausible = "less supported"
    else:
        plausible = "plausible but not established"
    return {
        "current_interpretation": [
            "The alert-delivery issue followed a monitoring firmware / alert config change.",
            f"{exposed_count} peer assets share the same monitoring firmware / alert config exposure.",
            f"{precursor_count} exposed peers show the same precursor signal.",
            f"{counterexample_count} exposed peers do not show the precursor signal.",
            f"{matching_failure_count} matching peer alert-delivery issue has been recorded.",
            f"A shared alert-delivery issue is {plausible}.",
        ],
        "why": [
            "Deployment and configuration evidence precede the incident.",
            "The same email/text alert delivery pattern appears near the E-stop event.",
            "Peer comparison finds exposed machines with and without the precursor.",
        ],
        "what_contradicts_this": [
            *evidence_state["counterevidence"],
            "16 exposed peers show no matching precursor signal.",
            "No peer alert-delivery failure is currently recorded.",
        ],
        "what_would_reduce_uncertainty": [
            "5-minute local controller and alert-delivery trace around the E-stop.",
            "override actor, reason and exact parameter changes.",
            "configuration diff for C16 -> C17.",
            "follow-up test outcome linked to the original decision.",
        ],
        "limitation": "Evidence synthesis uses facts already reconstructed by the backend. It does not create facts or establish causality.",
    }


def _review_status(evidence_state: dict[str, list[str]], reconstructability: ReconstructabilityReport) -> str:
    missing = [item for item in reconstructability.coverage if item.state == CoverageState.missing]
    if evidence_state["counterevidence"]:
        return "DECISION PENDING · COUNTEREVIDENCE PRESENT"
    if len(missing) >= 2:
        return "DECISION PENDING · EVIDENCE GAPS"
    return "DECISION PENDING"


def _frozen_decision(records: list[CanonicalEvidence], incident_time: datetime, knowledge_time: datetime) -> dict[str, Any]:
    known = [e for e in records if e.asset_id in ("crane-07", None) and e.ingested_at <= knowledge_time]
    return {
        "decision": "Hold deployment",
        "decision_time": LIVE_REVIEW_DECISION_TIME.isoformat(),
        "evidence_available_count": len(known),
        "known": [
            "monitoring firmware 4.9 and alert routing config C17 were active",
            "E-stop and alert-delivery latency were observed",
            "peer exposure existed across the fleet",
        ],
        "unknown": [
            "operator override reason",
            "local controller state during connectivity loss",
            "whether monitoring firmware/config affected alert delivery",
        ],
        "reason_entered_by_team": "Hold deployment until peer exposure and missing controller-state evidence are reviewed.",
        "historical_context_rule": "Later evidence can change the current conclusion, but it does not rewrite what was knowable at decision time.",
    }


def _historical_learning_pending() -> dict[str, Any]:
    return {
        "created": False,
        "headline": "Historical learning not generated yet",
        "note": "Outcome-linked history appears after new evidence and follow-up outcomes attach to the review.",
        "similar_contexts": 0,
        "outcomes": [],
    }


def _historical_learning_from_report(report: LearningReport) -> dict[str, Any]:
    return {
        "created": True,
        "headline": "Every decision makes the next review less cold-start",
        "similar_contexts": report.similar_contexts,
        "note": report.limitation,
        "outcomes": [item.model_dump(mode="json") for item in report.outcomes],
    }


def _synthetic_similar_episodes(signature: ContextSignature) -> list[SimilarEpisode]:
    rows = [
        ("episode-crane-11-202607031430", "crane-11", 4, "Continue investigation", "isolated alert config issue", False, "same monitoring firmware / alert config and precursor; no peer alert-delivery issue"),
        ("episode-crane-14-202607091120", "crane-14", 4, "Continue investigation", "isolated config issue", False, "same precursor, lower load envelope"),
        ("episode-crane-18-202607181620", "crane-18", 4, "Continue investigation", "isolated config issue", False, "same config activation path"),
        ("episode-crane-22-202607221010", "crane-22", 3, "Continue investigation", "isolated alert config issue", False, "same monitoring firmware / alert config, no alert-delivery issue"),
        ("episode-crane-27-202607291705", "crane-27", 3, "Continue investigation", "isolated config issue", False, "same precursor signal, different operator context"),
        ("episode-crane-31-202608021330", "crane-31", 3, "Continue investigation", "maintenance note corrected telemetry interpretation", False, "human assertion later contradicted by telemetry"),
        ("episode-crane-33-202608041440", "crane-33", 3, "Continue investigation", "no recurrence after limited test", False, "same missing local controller state"),
        ("episode-crane-34-202608060915", "crane-34", 3, "Continue investigation", "no recurrence after limited test", False, "same evidence gaps"),
        ("episode-crane-09-202607111015", "crane-09", 4, "Rollback", "resolved after rollback", False, "same monitoring firmware / alert config and repeated peer signal"),
        ("episode-crane-12-202607151515", "crane-12", 4, "Rollback", "resolved after rollback", False, "matching peer alert-delivery issue present"),
        ("episode-crane-16-202607261005", "crane-16", 3, "Rollback", "no clear improvement", True, "same change window, missing intervention reason"),
        ("episode-crane-19-202607301220", "crane-19", 3, "Rollback", "no clear improvement", True, "counterexamples existed before rollback"),
        ("episode-crane-21-202608031250", "crane-21", 3, "Rollback", "resolved after config revert", False, "config diff was available"),
        ("episode-crane-24-202607071155", "crane-24", 3, "Field inspection", "hardware-related", False, "same E-stop alarm, different monitoring firmware"),
        ("episode-crane-25-202607171350", "crane-25", 3, "Field inspection", "hardware-related", False, "load envelope exceeded prior validated range"),
        ("episode-crane-28-202607281040", "crane-28", 3, "Field inspection", "hardware-related", False, "operator reported mechanical drag"),
        ("episode-crane-30-202608011625", "crane-30", 3, "Field inspection", "hardware-related", False, "inspection found drive assembly wear"),
        ("episode-crane-32-202608050845", "crane-32", 2, "Field inspection", "no defect found", False, "weaker context match"),
    ]
    return [
        SimilarEpisode(
            episode_id=episode_id,
            asset_id=asset_id,
            similarity_score=score,
            previous_action=action,
            outcome=outcome,
            recurrence=recurrence,
            caveat=caveat,
        )
        for episode_id, asset_id, score, action, outcome, recurrence, caveat in rows
        if score >= 2 and (signature.firmware or signature.configuration)
    ]


def _summarize_outcomes(items: list[SimilarEpisode]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.outcome] = counts.get(item.outcome, 0) + 1
    outcome, count = max(counts.items(), key=lambda kv: kv[1])
    return f"{count} {outcome}"
