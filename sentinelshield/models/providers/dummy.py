from __future__ import annotations

import asyncio


class DummyProvider:
    name = "dummy"

    async def moderate(self, text: str) -> tuple[float, str | None]:
        await asyncio.sleep(0)  # simulate async
        score = 1.0 if "bad" in text.lower() else 0.0
        label = "BLOCK" if score > 0.5 else "ALLOW"
        return score, label


provider = DummyProvider()
