from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.orchestrator import build_orchestrator


router = APIRouter()
orc = build_orchestrator(api_path="/v1/general-guard")


class ModerationRequest(BaseModel):
    text: str


@router.post("/v1/general-guard")
async def moderate(req: ModerationRequest):
    resp = await orc.moderate(req.text)
    return resp
