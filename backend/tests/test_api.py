from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_climatology_without_data_is_graceful():
    r = client.get("/api/weather/climatology", params={"min_temp_c": -5})
    assert r.status_code == 200
    body = r.json()
    assert body["has_data"] is False and body["thresholds"]["min_temp_c"] == -5


def test_unknown_route_404():
    assert client.get("/api/weather/climatology", params={"route": "nope"}).status_code == 404


def test_collector_status_empty():
    r = client.get("/api/transit/collector-status")
    assert r.status_code == 200 and r.json()["departures"] == 0
