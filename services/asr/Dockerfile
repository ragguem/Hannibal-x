# syntax=docker/dockerfile:1.7
# Construit depuis la racine du dépôt :
#   docker build -f services/asr/Dockerfile --target cpu -t hannibal/asr:dev .   # poste, moteur scripté ou Whisper sur processeur
#   docker build -f services/asr/Dockerfile --target gpu -t hannibal/asr:gpu .   # serveur, Whisper sur GPU (CUDA 12, cuDNN 9)
# Les modèles ne sont pas dans l'image : ils sont téléchargés dans le volume /models au premier démarrage.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG CUDA_IMAGE=nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages/platform/pyproject.toml packages/platform/
COPY packages/contracts/pyproject.toml packages/contracts/
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/
COPY services/sim_bridge/pyproject.toml services/sim_bridge/
COPY services/asr/pyproject.toml services/asr/
COPY services/rerank/pyproject.toml services/rerank/
COPY services/doctrine/pyproject.toml services/doctrine/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package hannibal-asr --extra whisper
COPY packages/platform packages/platform
COPY packages/contracts packages/contracts
COPY services/asr services/asr
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package hannibal-asr --extra whisper

FROM ${PYTHON_IMAGE} AS cpu
ARG VERSION=0.5.0
LABEL org.opencontainers.image.title="hannibal-asr" org.opencontainers.image.version="${VERSION}"
RUN groupadd --system --gid 10001 hx && useradd --system --uid 10001 --gid hx --no-create-home hx \
    && mkdir /models && chown hx:hx /models
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/models HX_ASR_DEVICE=cpu
USER hx
EXPOSE 8200
HEALTHCHECK --interval=10s --timeout=3s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8200/health', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "--factory", "hannibal_asr.main:create_app", "--host", "0.0.0.0", "--port", "8200", "--no-access-log"]

# Ubuntu 24.04 fournit CPython 3.12, celui du venv construit plus haut.
FROM ${CUDA_IMAGE} AS gpu
ARG VERSION=0.5.0
LABEL org.opencontainers.image.title="hannibal-asr-gpu" org.opencontainers.image.version="${VERSION}"
RUN apt-get update && apt-get install -y --no-install-recommends python3.12 && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 hx && useradd --system --uid 10001 --gid hx --no-create-home hx \
    && mkdir /models && chown hx:hx /models
COPY --from=build /opt/venv/lib/python3.12/site-packages /opt/hx/site-packages
ENV PYTHONPATH=/opt/hx/site-packages PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/models HX_ASR_DEVICE=cuda
USER hx
EXPOSE 8200
HEALTHCHECK --interval=10s --timeout=3s --start-period=300s --retries=3 \
    CMD ["python3.12", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8200/health', timeout=2).status == 200 else 1)"]
CMD ["python3.12", "-m", "uvicorn", "--factory", "hannibal_asr.main:create_app", "--host", "0.0.0.0", "--port", "8200", "--no-access-log"]
