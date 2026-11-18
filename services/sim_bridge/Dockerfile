# syntax=docker/dockerfile:1.7
# Construit depuis la racine du dépôt :
#   docker build -f services/sim_bridge/Dockerfile --target kinematic -t hannibal/sim-bridge:dev .   # poste, sans ROS
#   docker build -f services/sim_bridge/Dockerfile --target ros -t hannibal/sim-bridge:ros .          # serveur LOTUSim
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG ROS_IMAGE=ros:jazzy-ros-base
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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package hannibal-sim-bridge
COPY packages/platform packages/platform
COPY packages/contracts packages/contracts
COPY packages/core packages/core
COPY services/sim_bridge services/sim_bridge
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package hannibal-sim-bridge

FROM ${PYTHON_IMAGE} AS kinematic
ARG VERSION=0.2.0
LABEL org.opencontainers.image.title="hannibal-sim-bridge" org.opencontainers.image.version="${VERSION}"
RUN groupadd --system --gid 10001 hx && useradd --system --uid 10001 --gid hx --no-create-home hx \
    && mkdir /data && chown hx:hx /data
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HX_SIM_BRIDGE_WORLD=kinematic
USER hx
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "--factory", "hannibal_sim_bridge.main:create_app", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]

# ROS 2 Jazzy (Ubuntu 24.04, CPython 3.12) : rclpy vient du système, lotusim_msgs est compilé depuis interfaces/.
FROM ${ROS_IMAGE} AS ros
ARG VERSION=0.2.0
LABEL org.opencontainers.image.title="hannibal-sim-bridge-ros" org.opencontainers.image.version="${VERSION}"
SHELL ["/bin/bash", "-c"]
COPY interfaces /ros/src/interfaces
RUN source /opt/ros/jazzy/setup.bash && cd /ros && colcon build --merge-install && rm -rf build log src
COPY --from=build /opt/venv/lib/python3.12/site-packages /opt/hx/site-packages
RUN groupadd --system --gid 10001 hx && useradd --system --uid 10001 --gid hx --no-create-home hx \
    && printf '#!/bin/bash\nsource /opt/ros/jazzy/setup.bash\nsource /ros/install/setup.bash\nexec "$@"\n' > /hx-entrypoint \
    && chmod +x /hx-entrypoint
ENV PYTHONPATH=/opt/hx/site-packages PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HX_SIM_BRIDGE_WORLD=ros
USER hx
EXPOSE 8100
ENTRYPOINT ["/hx-entrypoint"]
CMD ["python3", "-m", "uvicorn", "--factory", "hannibal_sim_bridge.main:create_app", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]
