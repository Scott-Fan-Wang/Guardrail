from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


class ModelSettings(BaseModel):
    active: str = "dummy"
    endpoint: str | None = None


class Settings(BaseModel):
    model: ModelSettings = ModelSettings()


settings = Settings()
