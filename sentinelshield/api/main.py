from __future__ import annotations

from fastapi import FastAPI

from .routers import moderation, admin

app = FastAPI(title="SentinelShield")
app.include_router(moderation.router)
app.include_router(admin.router)
