FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NC_AI_PROVIDER=local GEMINI_FREE_TIER_VERIFIED=false NC_DEPLOY_MODE=standby \
    HF_HOME=/models/huggingface HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_XET=1 WHISPER_MODEL=/models/whisper-small \
    NC_WORKER_CACHE_DIR=/data/cache TMPDIR=/data/tmp NC_HEALTH_FILE=/run/worker/health.json \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 CUDA_VISIBLE_DEVICES="" \
    PYTHONPATH=/app/worker:/app/deploy/worker
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates libgomp1 && \
    rm -rf /var/lib/apt/lists/*
COPY deploy/worker/requirements.lock /app/requirements.lock
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir --no-deps torch==2.9.0+cpu torchvision==0.24.0+cpu --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install --no-cache-dir --no-deps -r /app/requirements.lock && python -m pip check
COPY worker/noetharaclipz /app/worker/noetharaclipz
COPY deploy/worker/noetharaclipz_deploy /app/deploy/worker/noetharaclipz_deploy
RUN mkdir -p /run/worker /models /data/cache /data/tmp /reports && \
    chmod -R a+rX /app && \
    chown -R 62001:62001 /run/worker /models /data /reports
USER 62001:62001
WORKDIR /app
HEALTHCHECK --interval=30s --timeout=5s --start-period=240s --retries=3 \
    CMD ["python", "-m", "noetharaclipz_deploy.healthcheck"]
ENTRYPOINT ["python", "-m", "noetharaclipz_deploy.supervisor"]
