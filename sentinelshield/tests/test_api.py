from fastapi.testclient import TestClient

from sentinelshield.api.main import app

client = TestClient(app)

def test_moderate_allow():
    resp = client.post("/v1/moderate", json={"text": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["safe"] is True


def test_moderate_block_rule():
    resp = client.post("/v1/moderate", json={"text": "nazi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"
