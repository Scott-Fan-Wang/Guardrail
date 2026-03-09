from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from ...core.logger import logger

try:
    from transformers.pipelines import pipeline
except Exception as e:
    logger.warning("transformers not available: %s", e)
    pipeline = None


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return v if v > 0 else default
    except Exception:
        return default


_INFERENCE_MAX_WORKERS = _env_int("SENTINELSHIELD_INFERENCE_MAX_WORKERS", 4)
_INFERENCE_POOL = ThreadPoolExecutor(max_workers=_INFERENCE_MAX_WORKERS)
_INFERENCE_CONCURRENCY = _env_int("SENTINELSHIELD_INFERENCE_CONCURRENCY", _INFERENCE_MAX_WORKERS)


def _pipe_call(pipe, text: str):
    return pipe(text, truncation=True)


class LlamaGuard4_12BProvider:
    name = "llama_guard_4_12b"

    def __init__(self) -> None:
        self.pipe = None
        self._sem = asyncio.Semaphore(_INFERENCE_CONCURRENCY)
        if pipeline is None:
            return
        model_path = os.getenv(
            "SENTINELSHIELD_LLAMA_GUARD_MODEL_PATH",
            "/workspace/models/Llama-Guard-4-12B",
        )
        if not os.path.isdir(model_path):
            logger.error(
                "Llama Guard 4 12B model not found at '%s'. "
                "Run download.py on the host first, then re-mount ./models into the container.",
                model_path,
            )
            return
        try:
            self.pipe = pipeline(
                "text-classification",
                model=model_path,
                tokenizer=model_path,
            )
        except Exception as e:
            logger.warning("Failed to load Llama-Guard-4-12B model: %s", e)

    async def moderate(self, text: str) -> tuple[float, str | None]:
        score = 0.0
        label = None
        if self.pipe is None:
            await asyncio.sleep(0)
            return score, label
        async with self._sem:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(_INFERENCE_POOL, _pipe_call, self.pipe, text)
        if isinstance(res, list):
            res = res[0]
        if isinstance(res, dict):
            label = res.get("label",  None)
            score = float(res.get("score", 0.0))
        if label == 'LABEL_0':
            score = 1 - score
        return score, label

provider = LlamaGuard4_12BProvider() 