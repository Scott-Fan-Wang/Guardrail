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
    # If prompt is very long, split into chunks of up to 20,000 chars and check each
    if len(req.prompt) > 20000:
        max_len = 20000
        text = req.prompt
        collected_reasons = []
        for i in range(0, len(text), max_len):
            chunk = text[i : i + max_len]
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
