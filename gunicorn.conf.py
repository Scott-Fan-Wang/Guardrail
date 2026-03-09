"""Gunicorn configuration with per-worker Ascend NPU assignment.

Each Gunicorn worker is assigned a dedicated NPU by setting
SENTINELSHIELD_PROMPT_GUARD_DEVICE=npu:<id> in the post_fork hook.
All NPUs remain visible to every worker process; the pipeline is simply
initialised on the assigned card via the device string.

Why not ASCEND_RT_VISIBLE_DEVICES?
  Setting ASCEND_RT_VISIBLE_DEVICES after fork interferes with the Ascend HAL
  that was partially initialised in the master process, causing drvErr=87
  (BootRuntime failures).  Targeting npu:<id> directly avoids this entirely.

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

    Result for 8 workers on 8 NPUs:
        worker 1 → SENTINELSHIELD_PROMPT_GUARD_DEVICE=npu:0
        worker 2 → SENTINELSHIELD_PROMPT_GUARD_DEVICE=npu:1
        ...
        worker 8 → SENTINELSHIELD_PROMPT_GUARD_DEVICE=npu:7
    """
    npu_id = (worker.age - 1) % _num_npus

    # Target the assigned card directly via the device string.
    # All NPUs stay visible; no ASCEND_RT_VISIBLE_DEVICES manipulation is
    # needed, which avoids HAL re-initialisation conflicts after fork.
    os.environ["SENTINELSHIELD_PROMPT_GUARD_DEVICE"] = f"npu:{npu_id}"

    server.log.info("Worker %s → device npu:%s", worker.age, npu_id)
