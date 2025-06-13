from __future__ import annotations

import asyncio


class DummyProvider:
    name = "dummy"

    async def moderate(self, text: str) -> float:
        await asyncio.sleep(0)  # simulate async
        return 1.0 if "bad" in text.lower() else 0.0


provider = DummyProvider()
