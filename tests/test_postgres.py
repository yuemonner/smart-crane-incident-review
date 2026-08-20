from datetime import datetime, timezone

from app.postgres import AcecoPostgresReadOnlyConnector


class FakeCursor:
    def __init__(self):
        self.query = ""

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query, params=None): self.query = query
    def fetchall(self):
        if "FROM faults" in self.query:
            return [{"id": 9, "crane_uuid": "crane-real", "edge_uuid": "edge-1",
                     "motion_uuid": "motion-1", "fault_code": "UL3",
                     "fault_text": "Upper Limit Fault", "duration": 2,
                     "created_date": datetime(2026, 8, 10, tzinfo=timezone.utc), "sync_date": None}]
        return [{"id": 10, "crane_uuid": "crane-real", "edge_uuid": "edge-1",
                 "motion_uuid": "motion-1", "event_uuid": "event-1",
                 "event_name": "Motor Overspeed", "event_actions": [1, 4],
                 "created_date": datetime(2026, 8, 11, tzinfo=timezone.utc),
                 "is_synchronized": True}]


class FakeConnection:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def cursor(self): return FakeCursor()


def test_postgres_normalizes_only_operational_evidence(monkeypatch):
    connector = AcecoPostgresReadOnlyConnector("host", 5432, "db", "reader", "secret")
    monkeypatch.setattr(connector, "_connect", lambda: FakeConnection())
    events = connector.collect(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [event.id for event in events] == ["PG-faults-9", "PG-notifications-10"]
    assert {event.entity_id for event in events} == {"crane-real"}
    assert all("edge_users" not in event.source for event in events)
    assert connector.config["options"] == "-c default_transaction_read_only=on"
