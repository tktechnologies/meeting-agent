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

echo "✓ Starting API server..."
python -m agent.api
