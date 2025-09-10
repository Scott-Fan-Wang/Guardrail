from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/v1/healthz", status_code=204)
async def healthz():
    return
