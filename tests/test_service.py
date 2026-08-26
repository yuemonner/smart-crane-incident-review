from app.fixtures import INCIDENT_TIME, demo_events
from app.models import IncidentRequest
from app.service import EvidenceService


def analysis():
    service = EvidenceService(demo_events())
    investigation = service.investigate(IncidentRequest(entity_id="Crane-07", incident_time=INCIDENT_TIME))
    return investigation, service.where_else(investigation)


def test_where_else_expected_demo_counts_and_ranking():
    _, result = analysis()
    assert result.exposed_count == 7
    assert result.precursor_count == 3
    assert result.customer_count == 3
    assert all(x.precursor_detected for x in result.matches[:3])
    assert all(not x.precursor_detected for x in result.matches[3:])


def test_signature_is_traceable_to_evidence():
    _, result = analysis()
    assert result.signature.firmware == "0.36"
    assert result.signature.config_profile == "C17"
    assert "module_health_unhealthy_after_reconnect" in result.signature.precursor_pattern
    assert result.signature.derived_from_evidence_ids


def test_no_causality_overclaim():
    incident, result = analysis()
    assert any("caused" in x for x in incident.status.not_established)
    assert any("proves" in x for x in result.status.not_established)
    asserted = " ".join(incident.status.confirmed + result.status.confirmed).lower()
    assert "caused" not in asserted and "root cause" not in asserted


def test_last_known_good_is_explicit_and_traceable():
    incident, _ = analysis()
    lkg = incident.last_known_good
    assert lkg.established is True
    assert lkg.software_revision == "app 0.35"
    assert lkg.config_profile == "C16"
    assert lkg.evidence_ids == ["LKG-07-REV217"]
    assert "does not prove" in lkg.limitation


def test_device_vs_deployment_scope_does_not_overclaim():
    incident, _ = analysis()
    scope = incident.scope_assessment
    assert scope.classification == "peer_signals_observed"
    assert scope.peer_signal_count == 3
    assert scope.peer_incident_count == 0
    assert "no matching peer incident" in scope.explanation.lower()
