from __future__ import annotations

import asyncio
from fastapi import FastAPI

from .routers import moderation, admin, prompt_guard, chat_guard
from ..models.providers import get_provider
from ..core.logger import stop_logging

app = FastAPI(title="SentinelShield")
app.include_router(moderation.router)
app.include_router(admin.router)
app.include_router(prompt_guard.router)
app.include_router(chat_guard.router)


@app.on_event("shutdown")
async def _shutdown() -> None:
    qw3 = get_provider("qw3_guard")
    close = getattr(qw3, "close", None)
    if callable(close):
        res = close()
        if asyncio.iscoroutine(res):
            await res
    stop_logging()
