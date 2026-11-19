# syntax=docker/dockerfile:1.7
# Construit depuis la racine du dépôt : docker build -f services/doctrine/Dockerfile -t hannibal/doctrine:dev .
# Aucun modèle ni corpus dans l'image : Ollama sert les modèles, PostgreSQL (schéma v2) l'index.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
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
    uv sync --frozen --no-dev --no-install-workspace --package hannibal-doctrine
COPY packages/platform packages/platform
COPY packages/contracts packages/contracts
COPY packages/core packages/core
COPY services/doctrine services/doctrine
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package hannibal-doctrine

FROM ${PYTHON_IMAGE} AS runtime
ARG VERSION=0.6.0
LABEL org.opencontainers.image.title="hannibal-doctrine" org.opencontainers.image.version="${VERSION}"
RUN groupadd --system --gid 10001 hx && useradd --system --uid 10001 --gid hx --no-create-home hx
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER hx
EXPOSE 8400
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8400/health', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "--factory", "hannibal_doctrine.main:create_app", "--host", "0.0.0.0", "--port", "8400", "--no-access-log"]
