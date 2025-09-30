# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPINE_DB_PATH=/app/meeting-agent/spine_dev.sqlite3 \
    DEFAULT_ORG_ID=org_demo

WORKDIR /app
COPY . /app

# Install base deps (none declared explicitly) plus FastAPI stack
RUN pip install --no-cache-dir fastapi uvicorn

EXPOSE 8000

# Initialize DB (idempotent) then start API
CMD python -m agent.cli init-db --org ${DEFAULT_ORG_ID} && \
    python -m agent.api
