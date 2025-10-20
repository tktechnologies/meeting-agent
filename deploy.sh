#!/bin/bash

# Build and push meeting-agent Docker image to Azure Container Registry
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

log_info "Building and pushing $IMAGE_NAME:$TAG to $ACR_NAME.azurecr.io..."

# Login to ACR
log_info "Logging in to Azure Container Registry..."
az acr login --name "$ACR_NAME"

# Build the Docker image
log_info "Building Docker image..."
docker build -t "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}" .

# Push to ACR
log_info "Pushing image to ACR..."
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}"

log_info "✅ Deployment complete!"
echo ""
echo "Image pushed to: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}"
echo ""
echo "Next steps:"
echo "1. Go to Azure Portal"
echo "2. Navigate to your Container App: meeting-agent"
echo "3. Click 'Create new revision'"
echo "4. Select image: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${TAG}"
echo "5. Configure environment variables if needed"
echo "6. Create the revision"
echo ""
echo "Environment variables to set in Azure Portal:"
echo "  - OPENAI_API_KEY"
echo "  - TAVILY_API_KEY"
echo "  - USE_MONGODB_STORAGE=true"
echo "  - CHAT_AGENT_URL=https://stokai-dev.azurewebsites.net"
echo "  - SERVICE_TOKEN=<your-service-token>"
echo "  - DEFAULT_ORG_ID=<your-org-id>"
echo "  - ALLOWED_ORIGINS=https://stokai-dev.azurewebsites.net,https://meeting-agent.yellowdesert-a5580b23.eastus2.azurecontainerapps.io"
echo "  - PORT=8000"
