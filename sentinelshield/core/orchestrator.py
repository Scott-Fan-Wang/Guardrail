from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import List

from .schema import ModerationResponse, Reason
from .config import settings
from .logger import logger
from ..models import providers


class Rule:
    def __init__(self, rule_id: str, pattern: str, action: str):
        self.id = rule_id
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.action = action

    def match(self, text: str) -> bool:
        return bool(self.regex.search(text))


class RuleEngine:
    def __init__(self, rules_path: Path):
        self.rules: List[Rule] = []
        self.load_rules(rules_path)

    def load_rules(self, path: Path) -> None:
        if not path.exists():
            logger.warning("Rules path %s does not exist", path)
            return
        with open(path, "r") as f:
            data = yaml.safe_load(f) or []
        for item in data:
            when = item.get("when", "")
            # naive parse: expecting content.match(regex)
            if when.startswith("content.match"):
                pattern = when[len("content.match("):-1]
                if pattern.startswith('r"') and pattern.endswith('"'):
                    pattern = pattern[2:-1]
                elif pattern.startswith("r'") and pattern.endswith("'"):
                    pattern = pattern[2:-1]
                rule = Rule(item.get("id"), pattern, item.get("then", "ALLOW"))
                self.rules.append(rule)

    def evaluate(self, text: str) -> Rule | None:
        for rule in self.rules:
            if rule.match(text):
                return rule
        return None


class Orchestrator:
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    async def moderate(self, text: str) -> ModerationResponse:
        rule = self.rule_engine.evaluate(text)
        reasons: List[Reason] = []
        if rule:
            reasons.append(Reason(engine="rule", id=rule.id))
            return ModerationResponse(
                safe=False,
                decision=rule.action,
                reasons=reasons,
                policy_version="v1",
                model_version=settings.model.active,
            )
        # call model provider
        provider = providers.get_provider(settings.model.active)
        result = await provider.moderate(text)
        reasons.append(
            Reason(engine="model", category="dummy", score=result)
        )
        decision = "BLOCK" if result >= 0.5 else "ALLOW"
        return ModerationResponse(
            safe=decision == "ALLOW",
            decision=decision,
            reasons=reasons,
            policy_version="v1",
            model_version=settings.model.active,
        )


def build_orchestrator() -> Orchestrator:
    rule_engine = RuleEngine(Path(__file__).resolve().parent.parent / "rules" / "blacklist.yml")
    return Orchestrator(rule_engine)
