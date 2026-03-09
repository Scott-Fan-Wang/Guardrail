# Use the official MindIE image as the base
FROM swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.1.RC1-800I-A2-py311-openeuler24.03-lts

# Set environment variable for ModelScope cache
ENV MODELSCOPE_CACHE=/workspace

# Set working directory (optional, adjust as needed)
WORKDIR /workspace

# Install required Python packages
RUN pip install --no-cache-dir fastapi uvicorn gunicorn pydantic httpx pyyaml pytest transformers modelscope aiohttp

# Copy your FastAPI application code into the container (adjust path as needed)
COPY ./sentinelshield /workspace/sentinelshield

# Default command (production-style, can be overridden)
# Use envs to tune: PORT, WEB_CONCURRENCY, TIMEOUT, GRACEFUL_TIMEOUT
CMD ["bash", "-lc", "gunicorn sentinelshield.api.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8001} --workers ${WEB_CONCURRENCY:-4} --timeout ${TIMEOUT:-120} --graceful-timeout ${GRACEFUL_TIMEOUT:-30}"]