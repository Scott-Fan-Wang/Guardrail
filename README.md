# SentinelShield Prototype

This repository provides a minimal prototype based on the project outline.
It exposes a simple FastAPI service with a rule engine and a dummy model
provider.

## Quick start

```bash
pip install fastapi uvicorn pydantic httpx pyyaml pytest transformers modelscope
pip install 'httpx<0.28' -U
uvicorn sentinelshield.api.main:app --reload
```

To quickly check the `llama_prompt_guard_2` model without running the API you can call the example script:

```bash
python examples/prompt_guard_cli.py "hello"
```

Then call the API:

```bash
curl -XPOST http://localhost:8000/v1/moderate -d '{"text": "hello"}' -H 'Content-Type: application/json'
```

```bash
curl -XPOST http://localhost:8000/v1/prompt-guard -d '{"prompt": "hello"}' -H 'Content-Type: application/json'
```

## Using Llama Prompt Guard 2

The project includes a wrapper for the public `LLM-Research/Llama-Prompt-Guard-2-86M` model.
You can test the provider locally without starting the API using the example script.
It creates an `Orchestrator` configured with `llama_prompt_guard_2` and prints the decision:

```bash
python examples/prompt_guard_cli.py "Your prompt here"
```

It will print a decision (`ALLOW` or `BLOCK`) and the model score. Higher scores indicate the prompt is likely unsafe.

The FastAPI endpoint `/v1/prompt-guard` already uses this provider. After starting the server
with `uvicorn` you can query the endpoint to get the moderation decision:

```bash
curl -XPOST http://localhost:8000/v1/prompt-guard \
     -d '{"prompt": "your prompt"}' \
     -H 'Content-Type: application/json'
```
