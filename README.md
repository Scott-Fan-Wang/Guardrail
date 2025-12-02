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
pip install fastapi uvicorn pydantic httpx pyyaml pytest transformers modelscope
pip install 'httpx<0.28' -U

uvicorn sentinelshield.api.main:app --reload --host 0.0.0.0 --port 8001
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
  guard-img-v1 \
  uvicorn sentinelshield.api.main:app --reload --host 0.0.0.0 --port 8001
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
