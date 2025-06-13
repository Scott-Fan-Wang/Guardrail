from __future__ import annotations

from . import dummy
try:
    from . import llama_prompt_guard
except Exception:
    llama_prompt_guard = None


_providers = {
    "dummy": dummy.provider,
    "llama_prompt_guard_2": getattr(llama_prompt_guard, "provider", dummy.provider),
}


def get_provider(name: str):
    return _providers.get(name, dummy.provider)
