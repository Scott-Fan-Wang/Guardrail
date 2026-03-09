# Use the official MindIE image as the base
FROM swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.1.RC1-800I-A2-py311-openeuler24.03-lts

# Set environment variable for ModelScope cache
ENV MODELSCOPE_CACHE=/workspace

# Set working directory (optional, adjust as needed)
WORKDIR /workspace

# Install required Python packages
RUN pip install --no-cache-dir fastapi uvicorn gunicorn pydantic httpx pyyaml pytest transformers modelscope aiohttp

# Copy application code and Gunicorn configuration
COPY ./sentinelshield /workspace/sentinelshield
COPY ./gunicorn.conf.py /workspace/gunicorn.conf.py

# Default command (production-style, can be overridden).
# gunicorn.conf.py handles bind/workers/timeout and assigns one Ascend NPU
# per worker via ASCEND_RT_VISIBLE_DEVICES in a post_fork hook.
# Tune behaviour with env vars: PORT, WEB_CONCURRENCY, TIMEOUT,
# GRACEFUL_TIMEOUT, ASCEND_NUM_DEVICES, SENTINELSHIELD_PROMPT_GUARD_DEVICE.
CMD ["bash", "-lc", "gunicorn sentinelshield.api.main:app -c /workspace/gunicorn.conf.py"]