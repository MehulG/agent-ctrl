# syntax=docker/dockerfile:1

FROM python:3.12-slim AS backend

ARG CTRL_DB_PATH=/data/ctrl.db
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

RUN mkdir -p /data
EXPOSE 8788
CMD ["ctrl", "approvals-serve", "--host", "0.0.0.0", "--port", "8788"]

# ---

FROM node:20 AS dashboard-builder

WORKDIR /app/dashboard
ARG NEXT_PUBLIC_CTRL_API_BASE=http://localhost:8788
ARG NEXT_PUBLIC_CTRL_DB_PATH=/data/ctrl.db
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
ARG NEXT_PUBLIC_CTRL_DB_PATH=/data/ctrl.db
ARG NEXT_PUBLIC_CTRL_SERVERS_PATH=demos/e2e_publish_market_report/configs/servers.yaml
ENV NODE_ENV=production \
    NEXT_PUBLIC_CTRL_API_BASE=${NEXT_PUBLIC_CTRL_API_BASE} \
    NEXT_PUBLIC_CTRL_DB_PATH=${NEXT_PUBLIC_CTRL_DB_PATH} \
    NEXT_PUBLIC_CTRL_SERVERS_PATH=${NEXT_PUBLIC_CTRL_SERVERS_PATH}

WORKDIR /app/dashboard

COPY --from=dashboard-builder /app/dashboard /app/dashboard
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
