from __future__ import annotations

import asyncio
from ..core.logger import logger

try:  # optional dependency
    from modelscope.hub.snapshot_download import snapshot_download
except Exception as e:  # pragma: no cover - optional dependency
    logger.warning("modelscope not available: %s", e)
    snapshot_download = None

try:
    from transformers import pipeline
except Exception as e:  # pragma: no cover - optional dependency
    logger.warning("transformers not available: %s", e)
    pipeline = None


class LlamaPromptGuard2Provider:
    name = "llama_prompt_guard_2"

    def __init__(self) -> None:
        self.pipe = None
        if pipeline is None:
            return
        model_id = "LLM-Research/Llama-Prompt-Guard-2-86M"
        model_path = None
        if snapshot_download:
            try:  # pragma: no cover - network required
                model_path = snapshot_download(model_id)
            except Exception as e:  # pragma: no cover - optional dependency
                logger.warning("Failed to download model from ModelScope: %s", e)
        if model_path is None:
            model_path = model_id
        try:  # pragma: no cover - optional dependency
            self.pipe = pipeline(
                "text-classification",
                model=model_path,
                tokenizer=model_path,
            )
        except Exception as e:  # pragma: no cover - optional dependency
            logger.warning("Failed to load Llama Prompt Guard 2 model: %s", e)

    async def moderate(self, text: str) -> float:
        if self.pipe is None:
            await asyncio.sleep(0)
            return 0.0
        res = self.pipe(text, truncation=True)
        if isinstance(res, list):
            res = res[0]
        return float(res.get("score", 0.0))


provider = LlamaPromptGuard2Provider()
