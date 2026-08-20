import asyncio

from app.smart_crane_source import SmartCraneSourceCatalog
from app.ado import AzureDevOpsReadOnlyConnector


def test_smart_crane_contracts_are_mapped(tmp_path):
    root = tmp_path / "smart_crane_sources"
    for rel in SmartCraneSourceCatalog.EXPECTED.values():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# source contract placeholder\n")

    result = SmartCraneSourceCatalog(str(root)).status()
    assert result["connected"]
    assert all(x["present"] for x in result["contracts"].values())
    assert "drive_fault" in result["evidence_mapping"]["motion_data"]


def test_ado_normalizes_real_api_shapes(monkeypatch):
    connector = AzureDevOpsReadOnlyConnector("org", "project", "secret")

    async def fake_get(path, params=None):
        if path == "git/repositories":
            return {"value": [{"id": "r1", "name": "Smart Crane.Edge.Modules"}]}
        if path.endswith("/commits"):
            return {"value": [{"commitId": "abc123", "comment": "SCS-1168 notification change",
                                "author": {"date": "2026-08-13T10:00:00Z", "name": "Yue"},
                                "remoteUrl": "https://dev.azure.com/commit/abc123"}]}
        if path.endswith("/pullrequests"):
            return {"value": []}
        if path == "build/builds":
            return {"value": [{"id": 42, "finishTime": "2026-08-13T11:00:00Z",
                                "definition": {"name": "Edge"}, "buildNumber": "42",
                                "result": "succeeded", "status": "completed",
                                "repository": {"name": "Smart Crane.Edge.Modules"}}]}
        raise AssertionError(path)

    monkeypatch.setattr(connector, "_get", fake_get)
    events = asyncio.run(connector.collect())
    assert {x.type.value for x in events} == {"commit", "build"}
    assert all(x.source_url or x.type.value == "build" for x in events)
