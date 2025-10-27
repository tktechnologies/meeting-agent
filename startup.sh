#!/bin/bash
# Smart startup script for meeting-agent
# Handles both SQLite and MongoDB modes

set -e

echo "Starting meeting-agent..."

if [ "$USE_MONGODB_STORAGE" = "true" ]; then
    echo "✓ MongoDB mode detected - skipping local DB initialization"
    echo "  Organizations will be created via chat-agent API on demand"
else
    echo "✓ SQLite mode detected - initializing local database"
    python -m agent.cli init-db --org "${DEFAULT_ORG_ID:-org_demo}"
fi

# Get port from environment (Azure Container Apps sets this automatically)
PORT="${PORT:-8000}"
echo "✓ Starting API server on port ${PORT}..."

# Use exec to replace shell process with uvicorn (proper signal handling)
# IMPORTANT: Do not use 'python -m agent.api' as it triggers __main__ block
exec uvicorn agent.api:app --host 0.0.0.0 --port "${PORT}" --workers 1
