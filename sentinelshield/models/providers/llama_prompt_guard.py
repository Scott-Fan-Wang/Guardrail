from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from ...core.logger import logger

try:
    from transformers import pipeline
except Exception as e:  # pragma: no cover - optional dependency
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


def _pipe_call_batch(pipe, texts: list[str]):
    return pipe(texts, truncation=True)


@dataclass(frozen=True)
class _QueuedReq:
    text: str
    fut: asyncio.Future


class InferenceBatcher:
    def __init__(
        self,
        pipe,
        *,
        executor: ThreadPoolExecutor,
        sem: asyncio.Semaphore,
        max_batch_size: int,
        max_wait_ms: int,
    ) -> None:
        self._pipe = pipe
        self._executor = executor
        self._sem = sem
        self._max_batch_size = max(1, max_batch_size)
        self._max_wait_s = max(0, max_wait_ms) / 1000.0

        self._queue: asyncio.Queue[_QueuedReq] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_runner(self) -> None:
        loop = asyncio.get_running_loop()
        if self._task is None or self._task.done() or self._loop is not loop:
            self._loop = loop
            self._task = loop.create_task(self._runner())

    async def predict_one(self, text: str):
        self._ensure_runner()
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self._queue.put(_QueuedReq(text=text, fut=fut))
        return await fut

    async def _runner(self) -> None:
        while True:
            first = await self._queue.get()
            batch: list[_QueuedReq] = [first]

            if self._max_wait_s > 0:
                deadline = asyncio.get_running_loop().time() + self._max_wait_s
                while len(batch) < self._max_batch_size:
                    timeout = deadline - asyncio.get_running_loop().time()
                    if timeout <= 0:
                        break
                    try:
                        nxt = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                        batch.append(nxt)
                    except asyncio.TimeoutError:
                        break
            else:
                while len(batch) < self._max_batch_size and not self._queue.empty():
                    batch.append(self._queue.get_nowait())

            texts = [r.text for r in batch]
            try:
                async with self._sem:
                    loop = asyncio.get_running_loop()
                    results = await loop.run_in_executor(self._executor, _pipe_call_batch, self._pipe, texts)

                if not isinstance(results, list) or len(results) != len(batch):
                    raise RuntimeError(f"Unexpected batch result shape: {type(results)} (len={getattr(results, '__len__', lambda: -1)()})")

                for req, res in zip(batch, results):
                    if not req.fut.cancelled():
                        req.fut.set_result(res)
            except Exception as e:
                for req in batch:
                    if not req.fut.cancelled():
                        req.fut.set_exception(e)


class LlamaPromptGuard2Provider:
    name = "llama_prompt_guard_2"

    def __init__(self) -> None:
        self.pipe = None
        self._sem = asyncio.Semaphore(_INFERENCE_CONCURRENCY)
        self._batcher: InferenceBatcher | None = None
        if pipeline is None:
            return
        model_path = os.getenv(
            "SENTINELSHIELD_PROMPT_GUARD_MODEL_PATH",
            "/workspace/models/Llama-Prompt-Guard-2-86M",
        )
        if not os.path.isdir(model_path):
            logger.error(
                "Llama Prompt Guard 2 model not found at '%s'. "
                "Run download.py on the host first, then re-mount ./models into the container.",
                model_path,
            )
            return
        device = os.getenv("SENTINELSHIELD_PROMPT_GUARD_DEVICE", "npu:0")
        try:  # pragma: no cover - optional dependency
            self.pipe = pipeline(
                "text-classification",
                model=model_path,
                tokenizer=model_path,
                device=device,
            )
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("Failed to load Llama Prompt Guard 2 model: %s", e)
            return

        batching_enabled = os.getenv("SENTINELSHIELD_PROMPT_GUARD_BATCHING", "1").lower() not in {"0", "false", "no"}
        if batching_enabled:
            max_batch_size = _env_int("SENTINELSHIELD_PROMPT_GUARD_MAX_BATCH_SIZE", 32)
            max_wait_ms = _env_int("SENTINELSHIELD_PROMPT_GUARD_MAX_WAIT_MS", 50)
            self._batcher = InferenceBatcher(
                self.pipe,
                executor=_INFERENCE_POOL,
                sem=self._sem,
                max_batch_size=max_batch_size,
                max_wait_ms=max_wait_ms,
            )

    async def moderate(self, text: str) -> tuple[float, str | None]:
        score = 0.0
        label = None
        if self.pipe is None:
            await asyncio.sleep(0)
            return score, label
        if self._batcher is not None:
            res = await self._batcher.predict_one(text)
        else:
            async with self._sem:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(_INFERENCE_POOL, _pipe_call, self.pipe, text)
        # print(f"Received list response: {res}")
        if isinstance(res, list):
            res = res[0]
        if isinstance(res, dict):
            label = res.get("label",  None)
            score = float(res.get("score", 0.0))
        if label == 'LABEL_0':
            score = 1 - score
        return score, label


provider = LlamaPromptGuard2Provider()
