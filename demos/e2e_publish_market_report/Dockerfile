# syntax=docker/dockerfile:1

FROM python:3.12-slim AS backend

ARG CTRL_DB_PATH=ctrl.db
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CTRL_DB_PATH=${CTRL_DB_PATH}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock README.md ./
COPY ctrl ./ctrl
COPY demos ./demos
COPY configs ./configs
COPY docs ./docs
COPY migrations ./migrations

RUN pip install --no-cache-dir .

RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'DB_PATH="${CTRL_DB_PATH:-ctrl.db}"' \
    'SERVERS_PATH="${CTRL_SERVERS_PATH:-configs/servers.yaml}"' \
    'POLICY_PATH="${CTRL_POLICY_PATH:-configs/policy.yaml}"' \
    'if command -v ctrl >/dev/null 2>&1; then' \
    '  ctrl validate-config --servers "$SERVERS_PATH" --policy "$POLICY_PATH" --db "$DB_PATH"' \
    'fi' \
    'exec "$@"' \
    > /usr/local/bin/ctrl-entrypoint.sh \
    && chmod +x /usr/local/bin/ctrl-entrypoint.sh

RUN mkdir -p /data
EXPOSE 8788
ENTRYPOINT ["ctrl-entrypoint.sh"]
CMD ["ctrl", "approvals-serve", "--host", "0.0.0.0", "--port", "8788"]

# ---

FROM node:20 AS dashboard-builder

WORKDIR /app/dashboard
ARG NEXT_PUBLIC_CTRL_API_BASE=http://localhost:8788
ARG NEXT_PUBLIC_CTRL_DB_PATH=ctrl.db
ARG NEXT_PUBLIC_CTRL_SERVERS_PATH=demos/e2e_publish_market_report/configs/servers.yaml
ENV NEXT_PUBLIC_CTRL_API_BASE=${NEXT_PUBLIC_CTRL_API_BASE} \
    NEXT_PUBLIC_CTRL_DB_PATH=${NEXT_PUBLIC_CTRL_DB_PATH} \
    NEXT_PUBLIC_CTRL_SERVERS_PATH=${NEXT_PUBLIC_CTRL_SERVERS_PATH}

COPY dashboard/package*.json dashboard/yarn.lock* ./
RUN npm ci

COPY dashboard .
RUN npm run build

# ---

FROM node:20-slim AS dashboard

ARG NEXT_PUBLIC_CTRL_API_BASE=http://localhost:8788
ARG NEXT_PUBLIC_CTRL_DB_PATH=ctrl.db
ARG NEXT_PUBLIC_CTRL_SERVERS_PATH=demos/e2e_publish_market_report/configs/servers.yaml
ENV NODE_ENV=production \
    NEXT_PUBLIC_CTRL_API_BASE=${NEXT_PUBLIC_CTRL_API_BASE} \
    NEXT_PUBLIC_CTRL_DB_PATH=${NEXT_PUBLIC_CTRL_DB_PATH} \
    NEXT_PUBLIC_CTRL_SERVERS_PATH=${NEXT_PUBLIC_CTRL_SERVERS_PATH}

WORKDIR /app/dashboard

COPY --from=dashboard-builder /app/dashboard /app/dashboard
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
