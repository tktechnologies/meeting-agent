#!/bin/bash

# Deploy meeting-agent to Azure Container Apps
# Run this from Azure Cloud Shell after cloning the repository

set -e  # Exit on error

# Configuration
RESOURCE_GROUP="stokai-tk"
ENVIRONMENT="stok-ai"
APP_NAME="meeting-agent"
LOCATION="eastus2"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    log_error "Dockerfile not found. Please run this script from the meeting-agent directory."
    exit 1
fi

log_info "Starting deployment of $APP_NAME to Azure Container Apps..."

# Prompt for secrets if not set
if [ -z "$OPENAI_API_KEY" ]; then
    read -p "Enter OpenAI API Key: " OPENAI_API_KEY
fi

if [ -z "$TAVILY_API_KEY" ]; then
    read -p "Enter Tavily API Key: " TAVILY_API_KEY
fi

# Get chat-agent URL (required for MongoDB storage)
if [ -z "$CHAT_AGENT_URL" ]; then
    CHAT_AGENT_URL=$(az containerapp show --name chat-agent --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || echo "")
    if [ -n "$CHAT_AGENT_URL" ]; then
        CHAT_AGENT_URL="https://${CHAT_AGENT_URL}"
    else
        read -p "Enter Chat Agent URL (e.g., https://chat-agent.azurecontainerapps.io): " CHAT_AGENT_URL
    fi
fi

log_info "Deploying $APP_NAME using 'az containerapp up'..."

# Deploy using az containerapp up (handles ACR creation, build, and deployment)
az containerapp up \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENVIRONMENT" \
    --location "$LOCATION" \
    --source . \
    --target-port 8000 \
    --ingress external \
    --env-vars \
        "OPENAI_API_KEY=$OPENAI_API_KEY" \
        "TAVILY_API_KEY=$TAVILY_API_KEY" \
        "USE_MONGODB_STORAGE=true" \
        "CHAT_AGENT_URL=$CHAT_AGENT_URL" \
        "USE_LANGGRAPH_AGENDA=true" \
        "DEFAULT_ORG_ID=org_demo"

# Get the URL
APP_URL=$(az containerapp show \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv)

log_info "Deployment complete!"
log_info "App URL: https://$APP_URL"
log_info "Health check: https://$APP_URL/health"

echo ""
echo "Test the deployment with:"
echo "  curl https://$APP_URL/health"
