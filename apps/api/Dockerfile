# syntax=docker/dockerfile:1.7
# Construit depuis la racine du dépôt : docker build -f apps/api/Dockerfile -t hannibal/api:dev .
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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package hannibal-api
COPY packages/platform packages/platform
COPY packages/contracts packages/contracts
COPY packages/core packages/core
COPY apps/api apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package hannibal-api

FROM ${PYTHON_IMAGE} AS runtime
ARG VERSION=0.1.0
LABEL org.opencontainers.image.title="hannibal-api" org.opencontainers.image.version="${VERSION}"
RUN groupadd --system --gid 10001 hx && useradd --system --uid 10001 --gid hx --no-create-home hx \
    && mkdir -p /var/lib/hannibal/recordings && chown hx:hx /var/lib/hannibal/recordings
COPY --from=build /opt/venv /opt/venv
COPY apps/api/scenarios /app/scenarios
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HX_API_SCENARIOS_DIR=/app/scenarios
USER hx
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "--factory", "hannibal_api.socle.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]
