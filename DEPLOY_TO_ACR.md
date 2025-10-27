# Deploy Meeting Agent to Azure Container Registry

## Quick Deployment Steps

### 1. Build and Push Image to ACR

From Azure Cloud Shell or any machine with Azure CLI:

```bash
cd meeting-agent
./deploy.sh
```

Or with a specific tag:

```bash
./deploy.sh v1.2.3
```

This will:
- Use **ACR Build** (Azure's cloud build service - no Docker daemon required!)
- Build the Docker image in Azure's infrastructure
- Push to ACR as `acrstokai.azurecr.io/meeting-agent:latest`

**Why ACR Build?**
- ✅ Works in Azure Cloud Shell (no Docker daemon needed)
- ✅ Fast - builds in Azure datacenters close to your registry
- ✅ No need to install Docker locally
- ✅ Handles authentication automatically

### 2. Create New Revision in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **Container Apps** → **meeting-agent**
3. Click **"Revision management"** in left sidebar
4. Click **"Create new revision"**
5. Under **Container image**, select:
   - **Registry**: `acrstokai.azurecr.io`
   - **Image**: `meeting-agent`
   - **Tag**: `latest` (or your custom tag)
6. Verify **Environment variables** are set (see below)
7. Click **"Create"**

### 3. Required Environment Variables

Make sure these are configured in the Container App:

```
OPENAI_API_KEY=sk-proj-...
TAVILY_API_KEY=tvly-dev-...
USE_MONGODB_STORAGE=true
CHAT_AGENT_URL=https://stokai-dev.azurewebsites.net
SERVICE_TOKEN=<your-service-token>
DEFAULT_ORG_ID=org_2r1L8uEJP47iqA7MqHlCEwgWmjL
ALLOWED_ORIGINS=https://stokai-dev.azurewebsites.net,https://meeting-agent.yellowdesert-a5580b23.eastus2.azurecontainerapps.io
PORT=8000
```

### 4. Verify Deployment

After the revision is created:

1. Check **"Log stream"** in Azure Portal for startup logs
2. Should see:
   ```
   [db_router] Using MongoDB storage via Chat Agent API
   [MongoDB] init_db called - no action required
   Initialized Spine DB and ensured org 'org_...'
   Uvicorn running on http://0.0.0.0:8000
   ```
3. Test the endpoint:
   ```bash
   curl https://meeting-agent.yellowdesert-a5580b23.eastus2.azurecontainerapps.io/health
   ```

## Troubleshooting

### Image Not Found
- Check image exists: `az acr repository show -n acrstokai --image meeting-agent:latest`
- List all tags: `az acr repository show-tags -n acrstokai --repository meeting-agent`

### Container Crash Loop
- Check logs in Azure Portal → Container App → Log stream
- Common issues:
  - Missing environment variables (especially `OPENAI_API_KEY`, `CHAT_AGENT_URL`)
  - Wrong `SERVICE_TOKEN`
  - Network connectivity issues to chat-agent

### CORS Errors
- Verify `ALLOWED_ORIGINS` includes both frontend and meeting-agent URLs
- Ensure no trailing slashes in URLs

## Local Testing (Optional)

If you have Docker installed locally, you can test before deploying:

```bash
# Build locally
docker build -t meeting-agent:test .

# Run locally
docker run -p 8001:8000 \
  -e OPENAI_API_KEY=sk-proj-... \
  -e TAVILY_API_KEY=tvly-dev-... \
  -e USE_MONGODB_STORAGE=true \
  -e CHAT_AGENT_URL=https://stokai-dev.azurewebsites.net \
  -e SERVICE_TOKEN=dev-token \
  -e DEFAULT_ORG_ID=org_demo \
  meeting-agent:test
```

Then test: `curl http://localhost:8001/health`

**Note**: Local testing is optional - ACR Build will work regardless of whether you have Docker installed

## What's Different from Previous Deploy Script?

**Old approach**: Script tried to create/update the Container App directly using `az containerapp up`  
**New approach**: Script uses `az acr build` to build and push Docker image to ACR

**Why the change?**
- ✅ Works in Azure Cloud Shell (no Docker daemon required)
- ✅ More control over revision creation in Azure Portal
- ✅ Easier to verify environment variables before deploying
- ✅ Simpler debugging if something goes wrong
- ✅ Faster - builds happen in Azure datacenters
- ✅ No need to install Docker locally

## Related Documentation

- `MEETING_AGENT_CONTAINER_CRASH_FIX.md` - Container crash root cause and fix
- `COMPLETE_DEPLOYMENT_CHECKLIST.md` - Full deployment guide for all services
- `CORS_FIX.md` - CORS configuration details
