from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.orchestrator import build_orchestrator


router = APIRouter()
orc = build_orchestrator()


class ModerationRequest(BaseModel):
    text: str


@router.post("/v1/moderate")
async def moderate(req: ModerationRequest):
    resp = await orc.moderate(req.text)
    return resp
