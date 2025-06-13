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
)


class PromptGuardRequest(BaseModel):
    prompt: str


@router.post("/v1/prompt-guard")
async def prompt_guard(req: PromptGuardRequest):
    resp = await orc.moderate(req.prompt)
    return resp
