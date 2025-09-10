from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path

from ...core.orchestrator import build_orchestrator

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
    resp = await orc.moderate(req.prompt)
    # If prompt is very long, double-check the last 10,000 characters
    if len(req.prompt) > 20000:
        tail = req.prompt[-10000:]
        tail_resp = await orc.moderate(tail)
        # Return the conservative result: block if either check blocks
        if not tail_resp.safe:
            return tail_resp
    return resp
