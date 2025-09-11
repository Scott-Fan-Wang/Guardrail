from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path

from ...core.orchestrator import build_orchestrator
from ...core.schema import ModerationResponse

router = APIRouter()
orc = build_orchestrator(
    model_name="llama_prompt_guard_2",
    rules_files=[
        Path(__file__).resolve().parent.parent.parent / "rules" / "whitelist.yml",
        Path(__file__).resolve().parent.parent.parent / "rules" / "blacklist.yml",
    ],
    api_path="/v1/prompt-guard",
)


class PromptGuardRequest(BaseModel):
    prompt: str


@router.post("/v1/prompt-guard")
async def prompt_guard(req: PromptGuardRequest):
    # If prompt is very long, split into chunks of up to 20,000 chars and check each from bottom to top
    if len(req.prompt) > 80000:
        max_len = 40000
        text = req.prompt
        collected_reasons = []
        # Calculate the number of chunks needed
        num_chunks = (len(text) + max_len - 1) // max_len
        # Iterate from the last chunk to the first chunk
        for chunk_idx in range(num_chunks - 1, -1, -1):
            start_idx = chunk_idx * max_len
            end_idx = min(start_idx + max_len, len(text))
            chunk = text[start_idx:end_idx]
            chunk_resp = await orc.moderate(chunk)
            # Conservative result: block immediately if any chunk is unsafe
            if not chunk_resp.safe:
                return chunk_resp
            collected_reasons.extend(chunk_resp.reasons)
        # All chunks safe -> return aggregated safe response
        return ModerationResponse(
            safe=True,
            decision="ALLOW",
            reasons=collected_reasons,
            model_version="chunked-pipeline",
        )
    else:
        resp = await orc.moderate(req.prompt)
    return resp
