from datetime import timedelta

from .models import (AssetMatch, EvidenceEvent, EvidenceMode, EvidenceType, ExposureSignature,
                     IncidentRequest, IncidentSummary, Investigation, KnowledgeStatus,
                     LastKnownGoodState, ScopeAssessment, WhereElseResult)

CHANGE_TYPES = {EvidenceType.commit, EvidenceType.pull_request, EvidenceType.build,
                EvidenceType.deployment, EvidenceType.test, EvidenceType.config_change}


class EvidenceService:
    def __init__(self, events: list[EvidenceEvent]):
        self.events = events

    def investigate(self, request: IncidentRequest) -> Investigation:
        start = request.incident_time - timedelta(hours=request.window_hours)
        end = request.incident_time + timedelta(hours=1)
        candidates = [e for e in self.events if start <= e.occurred_at <= end and
                      (e.entity_id in (None, request.entity_id))]
        if request.evidence_mode:
            candidates = [e for e in candidates if e.evidence_mode == request.evidence_mode]
        modes = {e.evidence_mode for e in candidates}
        if len(modes) > 1:
            # Never silently combine synthetic, cached, partial and live evidence.
            preferred = EvidenceMode.live if EvidenceMode.live in modes else EvidenceMode.cached
            candidates = [e for e in candidates if e.evidence_mode == preferred]
        priority = {EvidenceType.alarm: 0, EvidenceType.device_event: 1,
                    EvidenceType.config_change: 2, EvidenceType.deployment: 3,
                    EvidenceType.test: 4, EvidenceType.build: 5,
                    EvidenceType.pull_request: 6, EvidenceType.commit: 7,
                    EvidenceType.work_item: 8}
        timeline = sorted(candidates, key=lambda e: (e.occurred_at, priority.get(e.type, 9)))
        changes = [e for e in timeline if e.type in CHANGE_TYPES]
        alarm_events = [e for e in timeline if e.type == EvidenceType.alarm]
        alarm = bool(alarm_events)
        missing_delivery = any(
            e.attributes.get("notification_delivered") is False
            or e.attributes.get("alert_delivered") is False
            for e in timeline
        )
        status = KnowledgeStatus(
            confirmed=[x for x in [
                f"An alarm was recorded: {alarm_events[-1].title}." if alarm else None,
                "The email/text alert for the E-stop was not recorded as delivered." if missing_delivery else None,
                "Monitoring device firmware 4.9 and alert routing config C17 were activated within the investigation window."
                if any(e.type == EvidenceType.deployment and e.attributes.get("firmware") == "4.9" for e in timeline) else None,
            ] if x],
            not_established=[
                "A software/configuration change caused the incident.",
                "The incident was device-specific or deployment-wide.",
                "Matching evidence on another asset would prove a shared root cause.",
            ],
            evidence_gaps=[
                "A complete validated machine-state snapshot immediately before the incident is not present.",
                "Peer-device coverage may be incomplete for this evidence mode.",
            ],
        )
        retrieved = [e.retrieved_at for e in timeline if e.retrieved_at]
        work = next((e for e in reversed(timeline) if e.type == EvidenceType.work_item), None)
        coordination = work.attributes if work else {}
        last_known_good = self._last_known_good(timeline, request.incident_time)
        scope = self._scope_assessment(request, timeline)
        mode = next(iter({e.evidence_mode for e in timeline}), request.evidence_mode or EvidenceMode.partial)
        return Investigation(entity_id=request.entity_id, incident_time=request.incident_time,
                             timeline=timeline, what_changed=changes, status=status,
                             evidence_mode=mode,
                             freshest_source_at=max(retrieved) if retrieved else None,
                             stalest_source_at=min(retrieved) if retrieved else None,
                             coordination=coordination, last_known_good=last_known_good,
                             scope_assessment=scope)

    def _last_known_good(self, timeline: list[EvidenceEvent], incident_time) -> LastKnownGoodState:
        markers = [e for e in timeline if e.occurred_at < incident_time and
                   e.attributes.get("last_known_good") is True]
        if not markers:
            return LastKnownGoodState()
        marker = max(markers, key=lambda e: e.occurred_at)
        attrs = marker.attributes
        tests = [marker.title]
        if attrs.get("successful_test_cycles") is not None:
            tests.append(f"{attrs['successful_test_cycles']} successful test cycles")
        return LastKnownGoodState(established=True, observed_at=marker.occurred_at,
            software_revision=attrs.get("software_revision") or attrs.get("firmware"),
            config_profile=attrs.get("config_profile"), runtime_state=attrs.get("runtime_state"),
            test_evidence=tests, validated_by=attrs.get("validated_by"), evidence_ids=[marker.id],
            limitation="Last known good means explicitly observed and validated at this time; it does not prove every subsystem was healthy.")

    def _scope_assessment(self, request: IncidentRequest, timeline: list[EvidenceEvent]) -> ScopeAssessment:
        source_patterns = {p for e in timeline for p in
            ([e.attributes["pattern"]] if e.attributes.get("pattern") else e.attributes.get("patterns", []))}
        source_alarms = {e.attributes.get("alarm") or e.attributes.get("fault_code")
                         for e in timeline if e.type == EvidenceType.alarm}
        source_alarms.discard(None)
        peers = [e for e in self.events if e.evidence_mode == (request.evidence_mode or timeline[0].evidence_mode if timeline else EvidenceMode.partial)
                 and e.entity_id not in (None, request.entity_id)]
        peer_signals = [e for e in peers if e.attributes.get("pattern") in source_patterns or
                        any(p in source_patterns for p in e.attributes.get("patterns", []))]
        peer_incidents = [e for e in peers if e.type == EvidenceType.alarm and
                          (e.attributes.get("alarm") or e.attributes.get("fault_code")) in source_alarms]
        device_count = sum(1 for e in timeline if e.entity_id == request.entity_id and
                           e.type in (EvidenceType.alarm, EvidenceType.device_event))
        ids = [e.id for e in peer_signals + peer_incidents]
        if peer_incidents:
            classification = "broader_pattern_observed"
            explanation = "Matching incident evidence is present on peer devices; a shared cause is not established."
        elif peer_signals:
            classification = "peer_signals_observed"
            explanation = "Matching signals are present on peers, but no matching peer incident establishes deployment-wide impact."
        else:
            classification = "not_established"
            explanation = "Current evidence does not distinguish a device-specific issue from a deployment-wide issue. Peer coverage may be incomplete."
        return ScopeAssessment(classification=classification, device_evidence_count=device_count,
            peer_signal_count=len({e.entity_id for e in peer_signals}),
            peer_incident_count=len({e.entity_id for e in peer_incidents}),
            explanation=explanation, evidence_ids=ids)

    def incidents(self, mode: EvidenceMode | None = None) -> list[IncidentSummary]:
        alarm_events = [e for e in self.events if e.type == EvidenceType.alarm and e.entity_id]
        if mode:
            alarm_events = [e for e in alarm_events if e.evidence_mode == mode]
        return [IncidentSummary(id=e.id, entity_id=e.entity_id or "unknown", title=e.title,
                                incident_time=e.occurred_at, evidence_mode=e.evidence_mode,
                                source=e.source) for e in sorted(alarm_events, key=lambda x: x.occurred_at, reverse=True)]

    def where_else(self, investigation: Investigation) -> WhereElseResult:
        deployment = next((e for e in reversed(investigation.timeline)
                           if e.attributes.get("firmware") and e.attributes.get("config_profile")), None)
        precursors = sorted({pattern for e in investigation.timeline
                             for pattern in ([e.attributes["pattern"]] if e.attributes.get("pattern")
                                             else e.attributes.get("patterns", []))})
        signature = ExposureSignature(
            firmware=deployment.attributes.get("firmware") if deployment else None,
            config_profile=deployment.attributes.get("config_profile") if deployment else None,
            precursor_pattern=precursors,
            derived_from_evidence_ids=[e.id for e in investigation.timeline
                                       if e is deployment or e.attributes.get("pattern") or e.attributes.get("patterns")],
        )
        per_asset: dict[str, list[EvidenceEvent]] = {}
        for event in self.events:
            if event.evidence_mode != investigation.evidence_mode:
                continue
            if event.entity_id and event.entity_id != investigation.entity_id:
                per_asset.setdefault(event.entity_id, []).append(event)
        matches: list[AssetMatch] = []
        for entity, evidence in per_asset.items():
            inventory = next((e for e in evidence if e.attributes.get("firmware")), None)
            exposed = bool(inventory and inventory.attributes.get("firmware") == signature.firmware and
                           inventory.attributes.get("config_profile") == signature.config_profile)
            if not exposed:
                continue
            precursor_events = [e for e in evidence if (e.attributes.get("pattern") in precursors or
                                any(p in precursors for p in e.attributes.get("patterns", [])))]
            factors = [f"monitoring firmware {signature.firmware}", f"alert config {signature.config_profile}"]
            if precursor_events:
                factors.append("precursor telemetry")
            score = 70 + min(29, 20 if precursor_events else 0 + len(precursor_events) * 3)
            matches.append(AssetMatch(entity_id=entity, score=score, exposure_match=True,
                                      precursor_detected=bool(precursor_events), matched_factors=factors,
                                      evidence_ids=[e.id for e in ([inventory] + precursor_events) if e],
                                      customer=inventory.attributes.get("customer", "Unknown")))
        matches.sort(key=lambda m: (-m.score, m.entity_id))
        exposed = len(matches)
        precursor = sum(m.precursor_detected for m in matches)
        return WhereElseResult(
            source_entity_id=investigation.entity_id, signature=signature,
            exposed_count=exposed, precursor_count=precursor,
            customer_count=len({m.customer for m in matches}), matches=matches,
            status=KnowledgeStatus(
                confirmed=[f"{exposed} other assets share monitoring firmware / alert config exposure.",
                           f"{precursor} exposed assets show the selected precursor telemetry."],
                not_established=["These assets will experience the same incident.",
                                 "Shared exposure proves a shared root cause."],
                evidence_gaps=["No full matching alert-delivery issue is recorded on the matched peer assets.",
                               "Operational context is limited to the evidence sources connected for this mode."],
            ))
