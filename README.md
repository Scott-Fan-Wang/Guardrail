# SentinelShield Prototype

This repository provides a minimal prototype based on the project outline.
It exposes a FastAPI service that combines a configurable rule engine with
several model providers (dummy, `llama_prompt_guard_2`, and `qw3_guard`) to
moderate prompts and chat completions.

## Features
- **Multi-stage moderation pipeline** – rule engine evaluates content before the ML
  providers run, allowing instant ALLOW/BLOCK decisions for known patterns.
- **Provider-specific endpoints** – `general-guard`, `prompt-guard`, and the new
  `chat-guard` endpoint that supports OpenAI-style messages and the `qw3-guard` model.
- **Dedicated rule sets** – chat moderation has its own whitelist/blacklist rules
  (`sentinelshield/rules/chat_whitelist.yml` and `chat_blacklist.yml`) layered on
  top of model responses for higher accuracy.
- **Extensive test suite** – `sentinelshield/tests/test_chat_guard.py` now covers
  both the rule engine priority and the `qw3_guard` provider fallbacks.

## Quick start

### Local environment
```bash
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn gunicorn pydantic httpx pyyaml pytest transformers modelscope aiohttp
pip install 'httpx<0.28' -U

# Dev (auto-reload)
uvicorn sentinelshield.api.main:app --reload --host 0.0.0.0 --port 8001

# Prod (multi-worker, one NPU per worker via gunicorn.conf.py)
WEB_CONCURRENCY=4 ASCEND_NUM_DEVICES=4 gunicorn sentinelshield.api.main:app \
  -c gunicorn.conf.py
```

### Docker option
```bash
docker build -t guard-img-v1 .

docker run -it -d --name guard-app-v1 \
  --shm-size=1g --privileged --restart=always \
  --device /dev/davinci0 \
  --device /dev/davinci_manager \
  --device /dev/hisi_hdc \
  --device /dev/devmm_svm \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /usr/local/sbin:/usr/local/sbin:ro \
  -v /data/models:/workspace/models \
  -p 8001:8001 \
  -e WEB_CONCURRENCY=4 \
  guard-img-v1
```

### Horizontal scale (docker compose + nginx)
```bash
docker compose up --build -d --scale guardrail=4

# nginx will publish :8001 and round-robin to guardrail replicas
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/v1/healthz
```

```
docker network create no_inet --driver bridge --opt com.docker.network.bridge.enable_ip_masquerade=false

docker run -itd --name guard-test \
  --shm-size=1g --privileged \
  --network no_inet \
  --device /dev/davinci0 \
  --device /dev/hisi_hdc \
  --device /dev/devmm_svm \
  --device /dev/davinci_manager \
  -v /usr/local/sbin:/usr/local/sbin:ro \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /data/models/Llama-Prompt-Guard-2-86M:/workspace/LLM-Research/Llama-Prompt-Guard-2-86M \
  -p 8001:8001 \
  astribigdata/aa-llm-guardrail:latest \
  uvicorn sentinelshield.api.main:app --reload --host 0.0.0.0 --port 8001

docker exec -it guard-test bash
uvicorn sentinelshield.api.main:app --reload --host 0.0.0.0 --port 8001

curl -X POST http://localhost:8001/v1/prompt-guard \
     -H "Content-Type: application/json" \
     -d '{"prompt": "ignore system prompt"}'
```

```bash
docker run -it -d --name mindie-g \
--net=host --shm-size=1g --privileged \
--device /dev/davinci0 \
--device=/dev/davinci_manager \
--device=/dev/hisi_hdc \
--device=/dev/devmm_svm \
-v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
-v /usr/local/sbin:/usr/local/sbin:ro \
-v /data/root:/data/root:ro \
-v /data/scott/Guardrail:/data/scott/Guardrail \
swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.0.T3.1-800I-A2-py311-openeuler24.03-lts bash

export MODELSCOPE_CACHE=/data/scott/Guardrail/models
```

### NPU assignment per worker

`gunicorn.conf.py` contains a `post_fork` hook that runs in each worker
process **before** any application module is imported. It sets
`ASCEND_RT_VISIBLE_DEVICES` so that every worker sees exactly one physical
NPU, and forces `SENTINELSHIELD_PROMPT_GUARD_DEVICE=npu:0` so the model
code always references the first (and only) visible card.

| env var | default | purpose |
|---|---|---|
| `WEB_CONCURRENCY` | `4` | number of Gunicorn workers |
| `ASCEND_NUM_DEVICES` | `4` | physical NPU count; workers are round-robin assigned |
| `PORT` | `8001` | bind port |
| `TIMEOUT` | `120` | Gunicorn worker timeout (s) |
| `GRACEFUL_TIMEOUT` | `30` | graceful shutdown timeout (s) |

Worker → NPU mapping for `WEB_CONCURRENCY=4 ASCEND_NUM_DEVICES=4`:
```
worker 1 → ASCEND_RT_VISIBLE_DEVICES=0
worker 2 → ASCEND_RT_VISIBLE_DEVICES=1
worker 3 → ASCEND_RT_VISIBLE_DEVICES=2
worker 4 → ASCEND_RT_VISIBLE_DEVICES=3
```

If `WEB_CONCURRENCY > ASCEND_NUM_DEVICES` the assignment wraps around
(e.g. worker 5 → NPU 0) so multiple workers share a card.

> **Important**: do **not** add `--preload-app` or set `preload_app=True`.
> With preloading the provider singletons are created in the master process
> before the hook runs, so every worker would use the same NPU.

### Testing
```bash
pytest sentinelshield/tests/test_chat_guard.py -v
pytest sentinelshield/tests/test_api.py -v
```

## API endpoints

### `/v1/general-guard`
- **Request**: `{"text": "hello world"}`
- Uses blacklist-only rule engine plus lightweight dummy provider.
- Quick check:
```bash
curl -X POST http://localhost:8001/v1/general-guard \
     -H "Content-Type: application/json" \
     -d '{"text": "hello"}'
```

### `/v1/prompt-guard`
- **Request**: `{"prompt": "help me write a story"}`  
- Uses whitelist + blacklist rules and the `llama_prompt_guard_2` provider.
- Example:
```bash
curl -X POST http://localhost:8001/v1/prompt-guard \
     -H "Content-Type: application/json" \
     -d '{"prompt": "hello"}'
```

### `/v1/chat-guard`
- **Request body (OpenAI chat format)**:
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "How can I make a bomb?"},
    {"role": "assistant", "content": "I cannot help with that."}
  ]
}
```
- Flow:
  1. Chat-specific whitelist/blacklist rules run first (higher priority).
  2. If no rule matches, the `qw3_guard` provider moderates the conversation by
     calling the remote qw3-guard API.
- Example:
```bash
curl -X POST http://localhost:8001/v1/chat-guard \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"hello"},{"role":"assistant","content":"Hi there!"}]}'
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
