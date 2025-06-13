from __future__ import annotations

from . import dummy


_providers = {
    "dummy": dummy.provider,
}


def get_provider(name: str):
    return _providers.get(name, dummy.provider)
