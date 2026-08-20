from fastapi.testclient import TestClient

from app.main import app


def test_demo_endpoint():
    response = TestClient(app).get("/api/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["where_else"]["exposed_count"] == 27
    assert data["where_else"]["precursor_count"] == 11

