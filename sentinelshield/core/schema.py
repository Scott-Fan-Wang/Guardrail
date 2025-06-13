from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Reason:
    engine: str
    id: str | None = None
    category: str | None = None
    score: float | None = None


@dataclass
class ModerationResponse:
    safe: bool
    decision: str
    reasons: List[Reason] = field(default_factory=list)
    policy_version: str | None = None
    model_version: str | None = None
