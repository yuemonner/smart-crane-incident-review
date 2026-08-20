import asyncio
import pytest

from app.aceco_cloud import AcecoCloudReadOnlyConnector


def test_cloud_connector_starts_disconnected_and_stores_no_credentials():
    connector = AcecoCloudReadOnlyConnector("https://example.test")
    assert connector.connected is False
    assert not hasattr(connector, "password")
    assert not hasattr(connector, "email")


def test_cloud_connector_rejects_non_allowlisted_paths():
    connector = AcecoCloudReadOnlyConnector("https://example.test")
    connector._access_token = "ephemeral"
    with pytest.raises(ValueError, match="read-only allowlist"):
        asyncio.run(connector._get("/users/"))
    with pytest.raises(ValueError, match="read-only allowlist"):
        asyncio.run(connector._get("/cranes/1/publish/"))
