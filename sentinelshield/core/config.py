from __future__ import annotations

from pydantic import BaseModel
from typing import Literal, List, Dict


class ModelSettings(BaseModel):
    active: str = "dummy"
    endpoint: str | None = None


class APIConfig(BaseModel):
    """Configuration for a specific API endpoint"""
    providers: List[str] = ["dummy"]


class Settings(BaseModel):
    model: ModelSettings = ModelSettings()
    # API-specific configurations
    api_configs: Dict[str, APIConfig] = {
        "/v1/prompt-guard": APIConfig(providers=["llama_prompt_guard_2"]),
        "/v1/general-guard": APIConfig(providers=["dummy"]),
    }


settings = Settings()
