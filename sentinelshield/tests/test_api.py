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


def test_prompt_guard_allow():
    resp = client.post("/v1/prompt-guard", json={"prompt": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["safe"] is True


def test_prompt_guard_block_rule():
    resp = client.post("/v1/prompt-guard", json={"prompt": "nazi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"


def test_prompt_guard_whitelist():
    resp = client.post("/v1/prompt-guard", json={"prompt": "allowed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ALLOW"


def test_moderate_provider_block():
    resp = client.post("/v1/moderate", json={"text": "bad idea"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"

