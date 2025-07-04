from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import List
import time

from .schema import ModerationResponse, Reason
from .config import settings, APIConfig
from .logger import logger, system_logger, api_logger
from ..models import providers


class Rule:
    """Data class representing a moderation rule with pattern and action."""

    def __init__(self, rule_id: str, pattern: str, action: str):
        self.id = rule_id
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.action = action

    def match(self, text: str) -> bool:
        return bool(self.regex.search(text))


class RuleEngine:
    """Engine that loads and evaluates moderation rules against text."""

    def __init__(self, rules_paths: List[Path]):
        self.rules: List[Rule] = []
        for p in rules_paths:
            self.load_rules(p)

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
    """Coordinates content moderation using rules and machine learning models."""

    def __init__(self, rule_engine: RuleEngine, api_path: str = "/v1/moderate"):
        self.rule_engine = rule_engine
        self.api_path = api_path
        
        # Get the configured providers for this API endpoint
        api_config = settings.api_configs.get(api_path, APIConfig())
        configured_providers = api_config.providers
        
        # Only initialize the providers that are configured for this API
        self.providers = []
        for provider_name in configured_providers:
            provider = providers.get_provider(provider_name)
            if provider is not None:
                self.providers.append((provider_name, provider))
            else:
                logger.warning(f"Provider {provider_name} not available for API {api_path}")

    async def moderate(self, text: str) -> ModerationResponse:
        start_time = time.time()
        reasons: List[Reason] = []
        timings = {}
        # 1. Rule engine
        t0 = time.time()
        rule = self.rule_engine.evaluate(text)
        timings['rule_engine'] = time.time() - t0
        if rule:
            reasons.append(Reason(engine="rule", id=rule.id))
            resp = ModerationResponse(
                safe=rule.action == "ALLOW",
                decision=rule.action,
                reasons=reasons,
                policy_version="v1",
            )
            total_time = time.time() - start_time
            timings['total'] = total_time
            system_logger.info(f"Moderation timings: {timings}")
            api_logger.info(f"{self.api_path} request: {text}")
            api_logger.info(f"{self.api_path} response: {resp}")
            return resp
        # 2. Model providers pipeline
        for name, provider in self.providers:
            t1 = time.time()
            score, label = await provider.moderate(text)
            timings[name] = time.time() - t1
            reasons.append(Reason(engine=name, category=label, score=score))
            if score >= 0.5:
                resp = ModerationResponse(
                    safe=False,
                    decision="BLOCK",
                    reasons=reasons,
                    model_version=name,
                )
                total_time = time.time() - start_time
                timings['total'] = total_time
                system_logger.info(f"Moderation timings: {timings}")
                api_logger.info(f"{self.api_path} request: {text}")
                api_logger.info(f"{self.api_path} response: {resp}")
                return resp
        # If all pass
        resp = ModerationResponse(
            safe=True,
            decision="ALLOW",
            reasons=reasons,
            model_version="pipeline",
        )
        total_time = time.time() - start_time
        timings['total'] = total_time
        system_logger.info(f"Moderation timings: {timings}")
        api_logger.info(f"{self.api_path} request: {text}")
        api_logger.info(f"{self.api_path} response: {resp}")
        return resp


def build_orchestrator(
    model_name: str | None = None, rules_files: List[Path] | None = None, api_path: str = "/v1/moderate"
) -> Orchestrator:
    base = Path(__file__).resolve().parent.parent
    if rules_files is None:
        rules_files = [base / "rules" / "blacklist.yml"]
    rule_engine = RuleEngine(rules_files)
    if model_name:
        settings.model.active = model_name
    return Orchestrator(rule_engine, api_path)
