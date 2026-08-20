from app.local_evidence import LocalAcecoEvidenceConnector


def test_real_local_reliability_evidence_is_parsed_without_secrets(tmp_path):
    evidence = tmp_path / "aceco-edge-redis-log.txt"
    evidence.write_text(
        "\n".join([
            "device a395b49cb6d5",
            "2026-08-14 14:31:09 Redis Error 111 Connection refused",
            "2026-08-14 14:32:11 MultipleConnectionsException Multiple connections detected",
            "2026-08-14 14:33:00 password should never become evidence",
        ])
    )
    connector = LocalAcecoEvidenceConnector(str(tmp_path))
    events = connector.collect()
    patterns = {p for event in events for p in event.attributes["patterns"]}
    assert "redis_connection_refused" in patterns
    assert "iot_duplicate_connection" in patterns
    assert any(e.entity_id and "a395b49cb6d5" in e.entity_id for e in events)
    assert not any("password" in e.title.lower() or "token" in e.title.lower() for e in events)
