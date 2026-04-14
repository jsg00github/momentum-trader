import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "overall_status" in data
    assert "components" in data

def test_market_status():
    r = client.get("/api/market-status")
    # Backend returns either 200 or 503 if API is down, but 200 is expected normally.
    assert r.status_code in [200, 503]
    if r.status_code == 200:
        assert "indices" in r.json()

def test_universe():
    r = client.get("/api/universe")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
