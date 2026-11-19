# syntax=docker/dockerfile:1.7
# Bord : Caddy et la console React construite. Depuis la racine du dépôt :
#   docker build -f infra/bord/Dockerfile -t hannibal/proxy:dev .
ARG NODE_IMAGE=node:24-alpine
ARG CADDY_IMAGE=caddy:2.10-alpine

FROM ${NODE_IMAGE} AS web
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN --mount=type=cache,target=/pnpm/store pnpm install --frozen-lockfile --filter @hannibal-x/web
COPY apps/web apps/web
RUN pnpm --filter @hannibal-x/web build && rm -f apps/web/dist/mockServiceWorker.js

FROM ${CADDY_IMAGE} AS proxy
ARG VERSION=1.0.0
LABEL org.opencontainers.image.title="hannibal-proxy" org.opencontainers.image.version="${VERSION}"
COPY infra/bord/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /src/apps/web/dist /srv/web
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
EXPOSE 443
