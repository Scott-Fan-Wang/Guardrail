from dataclasses import dataclass, field, asdict
from typing import List

import orjson
from fastapi.responses import Response


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

    def to_response(self) -> Response:
        return Response(
            content=orjson.dumps(asdict(self)),
            media_type="application/json",
        )
