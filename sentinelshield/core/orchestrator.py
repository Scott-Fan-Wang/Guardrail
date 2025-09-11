from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import List
import time
import os

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
        self.rules_paths = rules_paths
        self._rules_cache: List[Rule] = []
        self._file_mtimes: dict[Path, float] = {}
        self._last_loaded_files: set[Path] = set()

    def _get_file_mtimes(self) -> dict[Path, float]:
        mtimes = {}
        for path in self.rules_paths:
            try:
                mtimes[path] = path.stat().st_mtime
            except Exception as e:
                logger.warning(f"Could not stat rule file {path}: {e}")
        return mtimes

    def _rules_need_reload(self) -> bool:
        current_mtimes = self._get_file_mtimes()
        if set(current_mtimes.keys()) != self._last_loaded_files:
            return True
        for path, mtime in current_mtimes.items():
            if self._file_mtimes.get(path) != mtime:
                return True
        return False

    def _load_rules(self) -> None:
        new_rules: List[Rule] = []
        current_mtimes = self._get_file_mtimes()
        changed_files = []
        for path in self.rules_paths:
            if not path.exists():
                logger.warning(f"Rules path {path} does not exist")
                continue
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f) or []
            except Exception as e:
                logger.error(f"Failed to load or parse rule file {path}: {e}")
                continue
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
                    new_rules.append(rule)
            # Detect changed files for logging
            if self._file_mtimes.get(path) != current_mtimes.get(path):
                changed_files.append((path, current_mtimes.get(path)))
        # Update cache and mtimes only if at least one file loaded successfully
        if new_rules:
            self._rules_cache = new_rules
            self._file_mtimes = current_mtimes
            self._last_loaded_files = set(current_mtimes.keys())
            if changed_files:
                for path, mtime in changed_files:
                    system_logger.info(f"Reloaded rules from {path} at mtime {mtime}")
        elif changed_files:
            # If all files failed, log but keep previous rules
            for path, mtime in changed_files:
                system_logger.warning(f"Failed to reload rules from {path} at mtime {mtime}; keeping previous rules.")

    def evaluate(self, text: str) -> Rule | None:
        if self._rules_need_reload() or not self._rules_cache:
            self._load_rules()
        for rule in self._rules_cache:
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
        
        # 1. Rule engine check first
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
        
        # Handle long prompts by checking first and last chunks
        if len(text) > 15000:
            return await self._moderate_long_prompt(text, start_time)

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

    async def _moderate_long_prompt(self, text: str, start_time: float) -> ModerationResponse:
        """Handle moderation for long prompts by checking first and last chunks."""
        collected_reasons = []
        timings = {}
        
        # Check last 10,000 characters
        last_chunk = text[-10000:]
        last_resp = await self._moderate_chunk(last_chunk, "last_chunk")
        if not last_resp.safe:
            return last_resp
        collected_reasons.extend(last_resp.reasons)

        # Check first 10,000 characters
        first_chunk = text[:10000]
        first_resp = await self._moderate_chunk(first_chunk, "first_chunk")
        if not first_resp.safe:
            return first_resp
        collected_reasons.extend(first_resp.reasons)

        # Both chunks safe -> return aggregated safe response
        total_time = time.time() - start_time
        timings['total'] = total_time
        resp = ModerationResponse(
            safe=True,
            decision="ALLOW",
            reasons=collected_reasons,
            model_version="first-last-pipeline",
        )
        system_logger.info(f"Long prompt moderation timings: {timings}")
        api_logger.info(f"{self.api_path} long prompt request: {text[:100]}...")
        api_logger.info(f"{self.api_path} long prompt response: {resp}")
        return resp

    async def _moderate_chunk(self, chunk: str, chunk_type: str) -> ModerationResponse:
        """Moderate a single chunk with rule engine first, then model checking."""
        reasons: List[Reason] = []
        
        # 1. Rule engine check first
        rule = self.rule_engine.evaluate(chunk)
        if rule:
            reasons.append(Reason(engine="rule", id=rule.id))
            return ModerationResponse(
                safe=rule.action == "ALLOW",
                decision=rule.action,
                reasons=reasons,
                policy_version="v1",
            )
        
        # 2. Model providers pipeline
        for name, provider in self.providers:
            score, label = await provider.moderate(chunk)
            reasons.append(Reason(engine=name, category=label, score=score))
            if score >= 0.5:
                return ModerationResponse(
                    safe=False,
                    decision="BLOCK",
                    reasons=reasons,
                    model_version=name,
                )
        
        # If all pass
        return ModerationResponse(
            safe=True,
            decision="ALLOW",
            reasons=reasons,
            model_version="pipeline",
        )


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
