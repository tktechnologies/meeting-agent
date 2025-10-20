#!/bin/bash

# Build and push meeting-agent Docker image to Azure Container Registry using ACR Build
# This method works in Azure Cloud Shell without requiring Docker daemon
# After running this, create a new revision in Azure Portal using this image

set -e  # Exit on error

# Configuration
ACR_NAME="acrstokai"
IMAGE_NAME="meeting-agent"
TAG="${1:-latest}"  # Use first argument as tag, default to 'latest'

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    log_error "Dockerfile not found. Please run this script from the meeting-agent directory."
    exit 1
fi

log_info "Building and pushing $IMAGE_NAME:$TAG to $ACR_NAME.azurecr.io using ACR Build..."
log_info "This uses Azure's cloud build service - no local Docker daemon required!"

# Use ACR build task to build and push in the cloud
log_info "Starting ACR build task..."
az acr build \
    --registry "$ACR_NAME" \
    --image "${IMAGE_NAME}:${TAG}" \
    --file Dockerfile \
    .

log_info "✅ Build and push complete!"
echo ""
echo "Image available at: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}"
echo ""
echo "Next steps:"
echo "1. Go to Azure Portal → Container Apps → meeting-agent"
echo "2. Click 'Revision management' → 'Create new revision'"
echo "3. Select container image:"
echo "   Registry: ${ACR_NAME}.azurecr.io"
echo "   Image: ${IMAGE_NAME}"
echo "   Tag: ${TAG}"
echo "4. Verify environment variables (see below)"
echo "5. Click 'Create'"
echo ""
echo "Required environment variables:"
echo "  ✓ OPENAI_API_KEY=sk-proj-..."
echo "  ✓ TAVILY_API_KEY=tvly-dev-..."
echo "  ✓ USE_MONGODB_STORAGE=true"
echo "  ✓ CHAT_AGENT_URL=https://stokai-dev.azurewebsites.net"
echo "  ✓ SERVICE_TOKEN=<your-service-token>"
echo "  ✓ DEFAULT_ORG_ID=<your-org-id>"
echo "  ✓ ALLOWED_ORIGINS=https://stokai-dev.azurewebsites.net,https://meeting-agent.yellowdesert-a5580b23.eastus2.azurecontainerapps.io"
echo "  ✓ PORT=8000"
echo ""
echo "Verify deployment:"
echo "  curl https://meeting-agent.yellowdesert-a5580b23.eastus2.azurecontainerapps.io/health"
