# Use the official MindIE image as the base
FROM swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.0.T3.1-800I-A2-py311-openeuler24.03-lts

# Set environment variable for ModelScope cache
ENV MODELSCOPE_CACHE=/workspace

# Set working directory (optional, adjust as needed)
WORKDIR /workspace

# Install required Python packages
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx pyyaml pytest transformers modelscope

# Copy your FastAPI application code into the container (adjust path as needed)
COPY ./sentinelshield /workspace/sentinelshield

# Default command (optional, can be overridden)
CMD ["bash"]

# CMD ["uvicorn", "sentinelshield.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001"]