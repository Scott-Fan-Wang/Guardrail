# SentinelShield Prototype

This repository provides a minimal prototype based on the project outline.
It exposes a simple FastAPI service with a rule engine and a dummy model
provider.

## Quick start

```bash
pip install fastapi uvicorn pydantic httpx pyyaml pytest
uvicorn sentinelshield.api.main:app --reload
```

Then call the API:

```bash
curl -XPOST http://localhost:8000/v1/moderate -d '{"text": "hello"}' -H 'Content-Type: application/json'
```
