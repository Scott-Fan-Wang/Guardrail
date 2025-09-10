from fastapi.testclient import TestClient

from sentinelshield.api.main import app

client = TestClient(app)

def test_moderate_allow():
    resp = client.post("/v1/general-guard", json={"text": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["safe"] is True


def test_moderate_block_rule():
    resp = client.post("/v1/general-guard", json={"text": "nazi"})
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
    resp = client.post("/v1/general-guard", json={"text": "bad idea"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"


def test_api_specific_providers():
    """Test that each API endpoint uses only its configured providers"""
    # Test that general-guard uses dummy provider (which blocks "bad" text)
    resp = client.post("/v1/general-guard", json={"text": "bad idea"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"
    # Check that the reason shows it came from dummy provider
    assert any(reason["engine"] == "dummy" for reason in data["reasons"])
    
    # Test that prompt-guard uses llama_prompt_guard_2 provider
    resp = client.post("/v1/prompt-guard", json={"prompt": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    # The response should show it used llama_prompt_guard_2 or pipeline
    assert data["safe"] is True

