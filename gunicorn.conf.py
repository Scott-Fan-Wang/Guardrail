"""Gunicorn configuration with per-worker Ascend NPU assignment.

Each Gunicorn worker is assigned a dedicated NPU via ASCEND_RT_VISIBLE_DEVICES,
so the worker process only sees one card and model code can always reference
device="npu:0" regardless of total NPU count on the host.

Key env vars (all optional, sensible defaults shown):
  PORT                   – bind port           (default: 8001)
  WEB_CONCURRENCY        – number of workers   (default: 4)
  TIMEOUT                – worker timeout s    (default: 120)
  GRACEFUL_TIMEOUT       – graceful quit s     (default: 30)
  ASCEND_NUM_DEVICES     – physical NPU count  (default: 4)
                           workers are round-robin assigned across this many NPUs.

DO NOT use --preload-app / preload_app=True together with this file.
The post_fork hook must run before the app modules are imported so that
the module-level provider singletons pick up the correct device.
"""

import os

# ---------------------------------------------------------------------------
# Server mechanics
# ---------------------------------------------------------------------------
bind = f"0.0.0.0:{os.getenv('PORT', '8001')}"
workers = int(os.getenv("WEB_CONCURRENCY", "8"))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GRACEFUL_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# NPU assignment
# ---------------------------------------------------------------------------
# Number of physical Ascend NPUs available on this host.
# Set ASCEND_NUM_DEVICES to match the number of /dev/davinciN devices passed
# to the container (e.g. ASCEND_NUM_DEVICES=8 for an 8-card machine).
_num_npus = int(os.getenv("ASCEND_NUM_DEVICES", "8"))


def post_fork(server, worker):
    """Assign each worker a dedicated NPU.

    worker.age is a 1-based counter incremented on every (re)spawn.
    Modulo arithmetic keeps the assignment in range even after crashes.

    Result for 4 workers on 4 NPUs:
        worker 1 → ASCEND_RT_VISIBLE_DEVICES=0  (npu:0)
        worker 2 → ASCEND_RT_VISIBLE_DEVICES=1  (npu:1)
        worker 3 → ASCEND_RT_VISIBLE_DEVICES=2  (npu:2)
        worker 4 → ASCEND_RT_VISIBLE_DEVICES=3  (npu:3)
    """
    npu_id = (worker.age - 1) % _num_npus

    # Restrict the worker to a single NPU (analogous to CUDA_VISIBLE_DEVICES).
    # With only one card visible the model always sees it as npu:0.
    os.environ["ASCEND_RT_VISIBLE_DEVICES"] = str(npu_id)
    os.environ["SENTINELSHIELD_PROMPT_GUARD_DEVICE"] = "npu:0"

    server.log.info(
        "Worker %s → NPU %s (ASCEND_RT_VISIBLE_DEVICES=%s)",
        worker.age,
        npu_id,
        npu_id,
    )
