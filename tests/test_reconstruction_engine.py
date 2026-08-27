from datetime import datetime, timedelta, timezone

from app.reconstruction import CoverageState, ReconstructionEngine, demo_learning_report, synthetic_operational_world
from app.reconstruction import live_reconstruction_report


DECISION_TIME = datetime(2026, 8, 14, 18, 32, tzinfo=timezone.utc)
KNOWLEDGE_TIME = datetime(2026, 8, 21, 10, 14, tzinfo=timezone.utc)


def engine():
    return ReconstructionEngine(synthetic_operational_world())


def test_reconstructs_firmware_at_incident_time():
    state = engine().state_at("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    assert state.fields["software"].value == "0.36"
    assert state.fields["configuration"].value == "C17"


def test_does_not_use_evidence_discovered_after_decision_time():
    state = engine().state_at("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    assert "CR07-COUNTER-NETWORK" in state.ignored_late_evidence_ids
    current = engine().state_at("crane-07", DECISION_TIME, DECISION_TIME + timedelta(days=8))
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
    assert result.exposed_count == 7
    assert result.precursor_count == 3


def test_includes_counterexamples():
    result = engine().match_peers("crane-07", DECISION_TIME)
    assert result.counterexample_count == 4
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
    assert report["machine_change_detected"]["application"] == "application 0.35 -> 0.36"
    assert "observed" in report["evidence_state"]
    assert "Evidence synthesis" in report["ai_reasoning_layer"]["limitation"]


def test_live_demo_preserves_historical_decision_after_late_evidence():
    before = live_reconstruction_report(9)
    after = live_reconstruction_report(10)
    assert before["team_decision"]["recorded"]["decision"] == "Continue remote troubleshooting and involve customer site IT"
    assert after["team_decision"]["recorded"]["decision"] == "Continue remote troubleshooting and involve customer site IT"
    assert after["new_evidence_notice"]["title"] == "New evidence changed the current conclusion"
    assert "before CR07-COUNTER-NETWORK" in after["new_evidence_notice"]["historical_context"]


def test_live_demo_where_else_includes_counterexamples():
    report = live_reconstruction_report(7)
    assert report["where_else"]["exposed_count"] == 7
    assert report["where_else"]["precursor_count"] == 3
    assert report["where_else"]["counterexample_count"] == 4


def test_live_demo_peer_failure_updates_current_view_without_rewriting_decision():
    report = live_reconstruction_report(11)
    assert report["active_event"]["title"] == "Crane-08 reports the same module-health issue"
    assert report["where_else"]["matching_failure_count"] == 1
    assert report["team_decision"]["recorded"]["decision"] == "Continue remote troubleshooting and involve customer site IT"
    assert "before the Crane-08 module-health issue" in report["new_evidence_notice"]["historical_context"]


def test_live_demo_generates_historical_learning_after_outcome():
    report = live_reconstruction_report(12)
    learning = report["historical_learning"]
    assert learning["created"] is True
    assert learning["similar_contexts"] == 18
    assert learning["outcomes"][0]["previous_action"] == "Continue investigation"
    assert "not a recommendation" in learning["note"].lower()


def test_builds_operational_episode_with_outcome_as_first_class_object():
    episode = engine().build_episode("crane-07", DECISION_TIME, KNOWLEDGE_TIME)
    assert episode.context_signature.firmware == "0.36"
    assert episode.context_signature.configuration == "C17"
    assert episode.machine_state.fields["software"].value == "0.36"
    assert "observed" in episode.knowledge_state
    assert episode.interventions[0].action == "network looked unstable"
    assert episode.outcome.result == "no recurrence after limited test"


def test_learning_report_is_structured_from_similar_episodes():
    report = demo_learning_report()
    learning = report["learning"]
    assert learning["similar_contexts"] == 18
    assert len(learning["similar_episodes"]) == 18
    assert {row["previous_action"] for row in learning["outcomes"]} == {
        "Continue investigation", "Revert to prior profile", "Field inspection", "Involve customer site IT"
    }
    assert "not a recommendation" in learning["limitation"].lower()


def test_context_graph_uses_review_relations_not_causality():
    graph = demo_learning_report()["graph"]
    relations = {edge["relation"] for edge in graph["edges"]}
    assert "decision_based_on" in relations
    assert "outcome_observed_after" in relations
    assert "caused_by" not in relations
    assert graph["limitation"].endswith("They do not establish causality.")
