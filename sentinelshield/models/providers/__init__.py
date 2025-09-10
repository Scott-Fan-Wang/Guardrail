from __future__ import annotations

from . import dummy

# Get all configured providers from settings
from ...core.config import settings
configured_providers = set()
for api_config in settings.api_configs.values():
    configured_providers.update(api_config.providers)

# Only import providers that are actually configured for any API
_providers = {
    "dummy": dummy.provider,
}

# Only import llama_prompt_guard if it's configured for any API
if "llama_prompt_guard_2" in configured_providers:
    try:
        from . import llama_prompt_guard
        _providers["llama_prompt_guard_2"] = getattr(llama_prompt_guard, "provider", dummy.provider)
    except Exception as e:
        print(f"Failed to import llama_prompt_guard: {e}")
        _providers["llama_prompt_guard_2"] = dummy.provider

# Only import llama_guard_4_12b if it's configured for any API
if "llama_guard_4_12b" in configured_providers:
    try:
        from . import llama_guard_4_12b
        _providers["llama_guard_4_12b"] = getattr(llama_guard_4_12b, "provider", dummy.provider)
    except Exception as e:
        print(f"Failed to import llama_guard_4_12b: {e}")
        _providers["llama_guard_4_12b"] = dummy.provider


def get_provider(name: str):
    return _providers.get(name, dummy.provider)
