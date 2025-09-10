from __future__ import annotations

import asyncio
from ...core.logger import logger

try:
    from modelscope.hub.snapshot_download import snapshot_download
except Exception as e:
    logger.warning("modelscope not available: %s", e)
    snapshot_download = None

try:
    from transformers.pipelines import pipeline
except Exception as e:
    logger.warning("transformers not available: %s", e)
    pipeline = None


class LlamaGuard4_12BProvider:
    name = "llama_guard_4_12b"

    def __init__(self) -> None:
        self.pipe = None
        if pipeline is None:
            return
        model_id = "LLM-Research/Llama-Guard-4-12B"
        model_path = None
        if snapshot_download:
            try:
                model_path = snapshot_download(model_id)
            except Exception as e:
                logger.warning("Failed to download model from ModelScope: %s", e)
        if model_path is None:
            model_path = model_id
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
        res = self.pipe(text, truncation=True)
        if isinstance(res, list):
            res = res[0]
        if isinstance(res, dict):
            label = res.get("label",  None)
            score = float(res.get("score", 0.0))
        if label == 'LABEL_0':
            score = 1 - score
        return score, label

provider = LlamaGuard4_12BProvider() 