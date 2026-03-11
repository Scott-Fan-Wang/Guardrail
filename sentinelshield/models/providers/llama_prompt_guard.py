from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from ...core.logger import logger


_TOKEN_LIMIT = 512
_WINDOW_TOKENS = 256


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

_CACHE_MISS = object()


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
        self._batch_queue: asyncio.Queue[list[_QueuedReq]] = asyncio.Queue()
        self._collector_task: asyncio.Task | None = None
        self._executor_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_runner(self) -> None:
        loop = asyncio.get_running_loop()
        if (
            self._collector_task is None
            or self._collector_task.done()
            or self._loop is not loop
        ):
            self._loop = loop
            self._collector_task = loop.create_task(self._collector_loop())
            self._executor_task = loop.create_task(self._executor_loop())

    async def predict_one(self, text: str):
        self._ensure_runner()
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self._queue.put(_QueuedReq(text=text, fut=fut))
        return await fut

    async def _collector_loop(self) -> None:
        """Continuously drain the request queue into batches."""
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

            await self._batch_queue.put(batch)

    async def _executor_loop(self) -> None:
        """Pull assembled batches and run inference, overlapping with collection."""
        while True:
            batch = await self._batch_queue.get()
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

        # Inference result cache (same pattern as RuleEngine._eval_cache)
        self._cache: OrderedDict[bytes, tuple[float, str | None]] = OrderedDict()
        self._cache_size = _env_int("SENTINELSHIELD_INFERENCE_CACHE_SIZE", 4096)

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

    def _cache_key(self, text: str) -> bytes:
        return hashlib.blake2b(text.encode("utf-8", errors="ignore"), digest_size=16).digest()

    def _cache_get(self, key: bytes) -> tuple[float, str | None] | object:
        if self._cache_size <= 0:
            return _CACHE_MISS
        try:
            v = self._cache.pop(key)
        except KeyError:
            return _CACHE_MISS
        self._cache[key] = v  # move to end
        return v

    def _cache_put(self, key: bytes, value: tuple[float, str | None]) -> None:
        if self._cache_size <= 0:
            return
        self._cache[key] = value
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _get_token_windows(self, text: str) -> tuple[str, str] | None:
        if self.pipe is None or getattr(self.pipe, "tokenizer", None) is None:
            return None

        tokenizer = self.pipe.tokenizer
        try:
            # Get full token ids without truncation; disable special tokens so windows correspond to content.
            encoded = tokenizer.encode(
                text,
                add_special_tokens=False,
                truncation=False,
            )
        except TypeError:
            # Older tokenizers may not support truncation kwarg; fall back to default behavior.
            encoded = tokenizer.encode(text, add_special_tokens=False)

        if len(encoded) <= _TOKEN_LIMIT:
            return None

        head_ids = encoded[:_WINDOW_TOKENS]
        tail_ids = encoded[-_WINDOW_TOKENS:]

        head_text = tokenizer.decode(head_ids, skip_special_tokens=True)
        tail_text = tokenizer.decode(tail_ids, skip_special_tokens=True)
        return head_text, tail_text

    async def _infer(self, text: str) -> tuple[float, str | None]:
        score = 0.0
        label: str | None = None

        if self.pipe is None:
            await asyncio.sleep(0)
            return score, label

        if self._batcher is not None:
            res = await self._batcher.predict_one(text)
        else:
            async with self._sem:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(
                    _INFERENCE_POOL, _pipe_call, self.pipe, text
                )

        if isinstance(res, list):
            res = res[0]
        if isinstance(res, dict):
            label = res.get("label", None)
            score = float(res.get("score", 0.0))
        if label == "LABEL_0":
            score = 1 - score
        return score, label

    async def moderate(self, text: str) -> tuple[float, str | None]:
        key = self._cache_key(text)
        cached = self._cache_get(key)
        if cached is not _CACHE_MISS:
            return cached  # type: ignore[return-value]

        windows = self._get_token_windows(text)
        if windows is not None:
            head_text, tail_text = windows
            head_res, tail_res = await asyncio.gather(
                self._infer(head_text),
                self._infer(tail_text),
            )
            # Choose the window with the higher score; on tie prefer the tail (more recent context).
            if head_res[0] > tail_res[0]:
                result = head_res
            else:
                result = tail_res
        else:
            result = await self._infer(text)

        self._cache_put(key, result)
        return result


provider = LlamaPromptGuard2Provider()
