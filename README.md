# SentinelShield Prototype

This repository provides a minimal prototype based on the project outline.
It exposes a simple FastAPI service with a rule engine and a dummy model
provider.

## Quick start
```bash
docker build -t guard-img .

docker run -it -d --name guard-app \
  --shm-size=1g --privileged \
  --device /dev/davinci0 \
  --device /dev/davinci_manager \
  --device /dev/hisi_hdc \
  --device /dev/devmm_svm \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /usr/local/sbin:/usr/local/sbin:ro \
  -v /data/models:/workspace/models \
  -p 8001:8001 \
  guard-img \
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
curl -XPOST http://172.16.21.51:8001/v1/prompt-guard -d '{"prompt": "hello"}' -H 'Content-Type: application/json'
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
