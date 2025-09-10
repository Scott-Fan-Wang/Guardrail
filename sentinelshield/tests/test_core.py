import asyncio
from pathlib import Path

from sentinelshield.core.orchestrator import build_orchestrator
from sentinelshield.core.config import settings


def test_build_orchestrator_sets_model():
    orig = settings.model.active
    orc = build_orchestrator(model_name="dummy", rules_files=[Path("sentinelshield/rules/blacklist.yml")])
    assert settings.model.active == "dummy"
    result = asyncio.run(orc.moderate("hello"))
    assert result.safe is True
    settings.model.active = orig


def test_orchestrator_multiple_rules():
    orc = build_orchestrator(
        model_name="dummy",
        rules_files=[
            Path("sentinelshield/rules/whitelist.yml"),
            Path("sentinelshield/rules/blacklist.yml"),
        ],
    )
    resp = asyncio.run(orc.moderate("allowed"))
    assert resp.decision == "ALLOW"
    resp2 = asyncio.run(orc.moderate("nazi"))
    assert resp2.decision == "BLOCK"
