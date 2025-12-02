from __future__ import annotations

from fastapi import FastAPI

from .routers import moderation, admin, prompt_guard, chat_guard

app = FastAPI(title="SentinelShield")
app.include_router(moderation.router)
app.include_router(admin.router)
app.include_router(prompt_guard.router)
app.include_router(chat_guard.router)
