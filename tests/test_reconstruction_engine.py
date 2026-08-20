from datetime import datetime, timedelta, timezone

from app.reconstruction import CoverageState, ReconstructionEngine, synthetic_operational_world
from app.reconstruction import live_reconstruction_report


DECISION_TIME = datetime(2026, 8, 14, 15, 32, tzinfo=timezone.utc)
KNOWLEDGE_TIME = datetime(2026, 8, 14, 16, 5, tzinfo=timezone.utc)


def engine():
    return ReconstructionEngine(synthetic_operational_world())


def test_reconstructs_firmware_at_incident_time():
    state = engine().state_at("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    assert state.fields["software"].value == "4.9"
    assert state.fields["configuration"].value == "C17"


def test_does_not_use_evidence_discovered_after_decision_time():
    state = engine().state_at("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    assert "CR07-COUNTER-NETWORK" in state.ignored_late_evidence_ids
    current = engine().state_at("crane-07", DECISION_TIME, DECISION_TIME + timedelta(hours=6))
    assert "CR07-COUNTER-NETWORK" not in current.ignored_late_evidence_ids


def test_distinguishes_observed_from_human_assertion():
    records = synthetic_operational_world()
    note = next(e for e in records if e.id == "CR07-HUMAN-NETWORK")
    alarm = next(e for e in records if e.id == "CR07-ALARM-ESTOP")
    assert note.assertion_type == "human_asserted"
    assert alarm.assertion_type == "observed"


def test_detects_missing_intervention_reason():
    report = engine().analyze_reconstructability("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    by_field = {item.field: item for item in report.coverage}
    assert by_field["Reason for intervention"].state == CoverageState.missing
    assert "not captured" in by_field["Reason for intervention"].explanation


def test_produces_before_after_config_diff():
    changes = engine().detect_changes("crane-07", DECISION_TIME)
    config = next(c for c in changes if c.subject == "config")
    assert config.before == "C16"
    assert config.after == "C17"


def test_finds_exposed_peer_assets_and_precursors():
    result = engine().match_peers("crane-07", DECISION_TIME)
    assert result.exposed_count == 27
    assert result.precursor_count == 11


def test_includes_counterexamples():
    result = engine().match_peers("crane-07", DECISION_TIME)
    assert result.counterexample_count == 16
    assert any(match.exposed and not match.precursor_detected for match in result.matches)


def test_never_promotes_correlation_to_causation():
    changes = engine().detect_changes("crane-07", DECISION_TIME)
    text = " ".join(c.model_dump_json() for c in changes).lower()
    assert "cause" not in text
    assert "caused" not in text


def test_preserves_superseded_hypothesis_as_late_counterevidence():
    state = engine().state_at("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    assert "CR07-HUMAN-NETWORK" not in state.ignored_late_evidence_ids
    assert "CR07-COUNTER-NETWORK" in state.ignored_late_evidence_ids


def test_generates_minimum_capture_recommendations():
    report = engine().analyze_reconstructability("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    capture = " ".join(report.minimum_future_capture)
    assert "runtime trace" in capture
    assert "manual override" in capture
    assert "configuration diff" in capture


def test_live_demo_creates_review_after_machine_change():
    report = live_reconstruction_report(5)
    assert report["new_review"]["created"] is True
    assert report["machine_change_detected"]["firmware"] == "4.8 -> 4.9"
    assert "observed" in report["evidence_state"]
    assert "AI explains evidence" in report["ai_reasoning_layer"]["limitation"]


def test_live_demo_preserves_historical_decision_after_late_evidence():
    before = live_reconstruction_report(8)
    after = live_reconstruction_report(9)
    assert before["team_decision"]["recorded"]["decision"] == "Hold deployment"
    assert after["team_decision"]["recorded"]["decision"] == "Hold deployment"
    assert after["new_evidence_notice"]["title"] == "New evidence changed the current conclusion"
    assert "before CR07-COUNTER-NETWORK" in after["new_evidence_notice"]["historical_context"]


def test_live_demo_where_else_includes_counterexamples():
    report = live_reconstruction_report(7)
    assert report["where_else"]["exposed_count"] == 27
    assert report["where_else"]["precursor_count"] == 11
    assert report["where_else"]["counterexample_count"] == 16
