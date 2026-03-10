from __future__ import annotations

import os

from uvicorn.workers import UvicornWorker


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return v if v >= 0 else default
    except Exception:
        return default


class ConfigurableUvicornWorker(UvicornWorker):
    """
    UvicornWorker with per-process concurrency limits.

    Under very high fan-in (e.g. 1500 concurrent clients), letting each worker
    accept unlimited in-flight requests leads to unbounded queuing and eventual
    TCP-level timeouts upstream. `limit_concurrency` causes Uvicorn to return 503
    when the in-flight limit is exceeded, applying fast backpressure.
    """

    CONFIG_KWARGS = {
        # Backpressure: return 503 when too many requests in-flight.
        "limit_concurrency": _env_int("SENTINELSHIELD_UVICORN_LIMIT_CONCURRENCY", 400),
        # Reduce memory use for websocket backlog (not used by this API).
        "ws_max_queue": _env_int("SENTINELSHIELD_UVICORN_WS_MAX_QUEUE", 0),
        # Avoid lifespan overhead under high load (no startup/shutdown hooks needed per request).
        "lifespan": os.getenv("SENTINELSHIELD_UVICORN_LIFESPAN", "off"),
    }

