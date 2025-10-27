# 🔬 Deep Research Agent Integration

Este documento descreve a integração entre o **Meeting Agent** e o **Deep Research Agent** para fornecer capacidades avançadas de pesquisa durante o planejamento de reuniões.

## 📋 Visão Geral

A integração permite que o Meeting Agent solicite pesquisas profundas ao Deep Research Agent quando:

1. **Contexto insuficiente**: Poucas informações disponíveis na base de conhecimento
2. **Tópico complexo**: Assunto requer pesquisa externa detalhada
3. **Alta prioridade**: Reunião estratégica necessita informações atualizadas
4. **Solicitação explícita**: Usuário pede pesquisa aprofundada

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    Meeting Agent                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LangGraph Workflow                                 │    │
│  │  ├── Intent Classification                          │    │
│  │  ├── Context Retrieval                              │    │
│  │  ├── 🆕 Research Orchestrator ◄─────┐              │    │
│  │  ├── Agenda Generation               │              │    │
│  │  └── Quality Review                  │              │    │
│  └──────────────────────────────────────┼──────────────┘    │
│                                         │                   │
│  ┌──────────────────────────────────────┼──────────────┐    │
│  │  Research Orchestrator               │              │    │
│  │  ├── Should use Deep Research?       │              │    │
│  │  ├── Call Deep Research Client ◄─────┘              │    │
│  │  └── Fallback to Basic Search (if fail)             │    │
│  └──────────────────────────────────────┬──────────────┘    │
│                                         │                   │
│  ┌──────────────────────────────────────┼──────────────┐    │
│  │  DeepResearchClient                  │              │    │
│  │  ├── HTTP Client (httpx)             │              │    │
│  │  ├── Circuit Breaker                 │              │    │
│  │  ├── Retry Logic                     │              │    │
│  │  └── Correlation ID Tracking         │              │    │
│  └──────────────────────────────────────┬──────────────┘    │
└─────────────────────────────────────────┼───────────────────┘
                                          │
                                          │ HTTP/REST
                                          │
┌─────────────────────────────────────────▼─────────────────┐
│              Deep Research Agent API                      │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  FastAPI Endpoints                                  │  │
│  │  ├── POST /research (sync)                          │  │
│  │  ├── POST /research/async (async)                   │  │
│  │  ├── GET /research/{job_id} (status)                │  │
│  │  └── GET /health (health check)                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  LangGraph Research Workflow                        │  │
│  │  ├── Plan Research Steps                            │  │
│  │  ├── Execute Web Search (Tavily)                    │  │
│  │  ├── Analyze & Synthesize                           │  │
│  │  └── Generate Report (Markdown)                     │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Adicione ao `.env` do Meeting Agent:

```bash
# ============================================================================
# Deep Research Agent Integration
# ============================================================================

# Enable/disable integration (feature flag)
DEEPRESEARCH_ENABLED=true

# Deep Research Agent API URL
# Development:
DEEPRESEARCH_API_URL=http://localhost:8000
# Production (Azure):
# DEEPRESEARCH_API_URL=https://deepresearch-agent.azurewebsites.net

# Model provider: "gemini" or "openai"
DEEPRESEARCH_MODEL=gemini

# Request timeout (seconds)
DEEPRESEARCH_TIMEOUT=300

# Research depth (3-10 steps)
DEEPRESEARCH_MAX_STEPS=5

# Optional API key for authentication
# DEEPRESEARCH_API_KEY=your-secret-key

# Whitelist orgs (comma-separated, empty = all orgs)
# DEEPRESEARCH_ORGS=org_acme,org_techcorp

# Minimum confidence to trigger (0.0-1.0)
DEEPRESEARCH_MIN_CONFIDENCE=0.6

# Fallback to basic search on error
DEEPRESEARCH_FALLBACK_BASIC=true
```

### 2. Deploy Local (Docker Compose)

```yaml
version: '3.8'

services:
  # Deep Research Agent
  deepresearch-agent:
    build: ../deepresearch-agent
    ports:
      - "8000:8000"
    environment:
      - MODEL_PROVIDER=gemini
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - PORT=8000
    networks:
      - agents-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  # Meeting Agent
  meeting-agent:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DEEPRESEARCH_ENABLED=true
      - DEEPRESEARCH_API_URL=http://deepresearch-agent:8000
      - DEEPRESEARCH_MODEL=gemini
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
    depends_on:
      deepresearch-agent:
        condition: service_healthy
    networks:
      - agents-network

networks:
  agents-network:
    driver: bridge
```

### 3. Deploy Azure (Independente)

Ambos os agentes são deployados como **Azure Container Apps** separados:

```bash
# 1. Deploy Deep Research Agent
az containerapp create \
  --name deepresearch-agent \
  --resource-group rg-agents \
  --environment agents-env \
  --image agentsregistry.azurecr.io/deepresearch-agent:latest \
  --target-port 8000 \
  --ingress internal \
  --secrets \
    google-api-key=$GOOGLE_API_KEY \
    tavily-api-key=$TAVILY_API_KEY

# 2. Deploy Meeting Agent com referência ao Deep Research
az containerapp create \
  --name meeting-agent \
  --resource-group rg-agents \
  --environment agents-env \
  --image agentsregistry.azurecr.io/meeting-agent:latest \
  --target-port 3000 \
  --ingress external \
  --env-vars \
    DEEPRESEARCH_ENABLED=true \
    DEEPRESEARCH_API_URL=https://deepresearch-agent.internal.agents-env.eastus2.azurecontainerapps.io
```

## 🔧 Uso no Código

### Verificar se está habilitado

```python
from agent import config

# Check global
if config.is_deepresearch_enabled():
    print("Deep Research enabled globally")

# Check for specific org
org_id = "org_acme"
if config.is_deepresearch_enabled_for_org(org_id):
    print(f"Deep Research enabled for {org_id}")
```

### Usar o cliente diretamente

```python
from agent.integrations.deepresearch_client import DeepResearchClient

# Create client
client = DeepResearchClient(
    base_url="http://localhost:8000",
    timeout=300
)

# Health check
if not client.health_check():
    print("Deep Research unavailable")
    # Use fallback

# Sync research
try:
    result = client.research_sync(
        topic="AI in Healthcare 2025",
        model_provider="gemini",
        max_steps=5,
        correlation_id="meeting-123"
    )
    
    print(f"Report:\n{result['report']}")
    print(f"Quality: {result['avg_quality']}/10")
    print(f"Time: {result['execution_time']}s")
    
except DeepResearchTimeoutError:
    print("Research timed out, using basic search")
    
except DeepResearchUnavailableError:
    print("Service unavailable, circuit breaker open")
```

### Async research (para tópicos complexos)

```python
# Start async research
job_id = client.research_async_start(
    topic="Quantum Computing Applications in Finance",
    model_provider="gemini"
)

print(f"Research started: {job_id}")

# Poll status (or use wait)
import time

while True:
    status = client.research_async_status(job_id)
    
    if status['status'] == 'completed':
        result = status['result']
        print(f"Completed!\n{result['report']}")
        break
    
    elif status['status'] == 'failed':
        print(f"Failed: {status['error']}")
        break
    
    print(f"Status: {status['status']}")
    time.sleep(5)

# Or use blocking wait
result = client.research_async_wait(
    job_id=job_id,
    poll_interval=5.0,
    max_wait=600.0
)
```

## 🛡️ Resiliência e Fallback

### Circuit Breaker

O cliente implementa **circuit breaker** para prevenir sobrecarga:

- ✅ **Fechado (Normal)**: Requisições passam normalmente
- ⚠️ **Aberto (Falha)**: Após 5 falhas consecutivas, para de tentar por 60s
- 🔄 **Semi-Aberto (Teste)**: Após timeout, tenta uma requisição de teste

```python
from agent.integrations.deepresearch_client import DeepResearchUnavailableError

try:
    result = client.research_sync(topic)
except DeepResearchUnavailableError as e:
    # Circuit breaker aberto
    logger.warning(f"Circuit breaker open: {e}")
    # Use fallback básico
    result = basic_search(topic)
```

### Retry com Exponential Backoff

Erros transitórios (timeout, network) são retentados automaticamente:

- **Tentativa 1**: Imediata
- **Tentativa 2**: Após 2 segundos
- **Tentativa 3**: Após 4 segundos
- **Tentativa 4**: Após 8 segundos (máximo)

```python
# Configurar retry customizado
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),  # Mais tentativas
    wait=wait_exponential(min=1, max=20)  # Backoff mais longo
)
def custom_research(topic):
    return client.research_sync(topic)
```

### Fallback Strategy

```python
def research_with_fallback(topic: str, org_id: str) -> dict:
    """
    Tenta Deep Research, fallback para básico se falhar.
    """
    # 1. Check if enabled
    if not config.is_deepresearch_enabled_for_org(org_id):
        return basic_search(topic)
    
    # 2. Try Deep Research
    try:
        client = DeepResearchClient()
        result = client.research_sync(topic)
        
        return {
            'report': result['report'],
            'source': 'deepresearch',
            'quality': result['avg_quality']
        }
    
    except Exception as e:
        logger.error(f"Deep Research failed: {e}, using fallback")
        
        # 3. Fallback to basic search
        basic_result = basic_search(topic)
        
        return {
            'report': basic_result,
            'source': 'basic',
            'quality': 5.0
        }
```

## 📊 Monitoramento

### Health Check Endpoint

```bash
# Check Meeting Agent health
curl http://localhost:3000/health

# Check Deep Research Agent health
curl http://localhost:8000/health
```

### Métricas do Deep Research

```bash
curl http://localhost:8000/metrics
```

Retorna:
```json
{
  "total_requests": 150,
  "successful_requests": 142,
  "failed_requests": 8,
  "avg_execution_time": 45.3,
  "cache_hit_rate": 0.15,
  "uptime_seconds": 86400
}
```

### Logs Estruturados

```python
import logging

logger = logging.getLogger(__name__)

# Logs incluem correlation_id para rastreamento
logger.info(
    "Deep Research completed",
    extra={
        "correlation_id": "meeting-123",
        "topic": "AI Healthcare",
        "quality": 8.5,
        "execution_time": 42.1
    }
)
```

### Azure Application Insights

Ambos os agentes enviam telemetria para Application Insights:

```python
from opencensus.ext.azure.log_exporter import AzureLogHandler

logger.addHandler(AzureLogHandler(
    connection_string=os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
))
```

## 🧪 Testes

### Teste Manual

```bash
# 1. Start Deep Research Agent
cd deepresearch-agent
python -m uvicorn api.main:app --reload --port 8000

# 2. Test health
curl http://localhost:8000/health

# 3. Test research (sync)
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "AI in Healthcare",
    "model_provider": "gemini",
    "max_steps": 3
  }'

# 4. Start Meeting Agent
cd ../meeting-agent-main
python -m uvicorn agent.api:app --reload --port 3000

# 5. Test integration
curl -X POST http://localhost:3000/agenda/plan-nl \
  -H "Content-Type: application/json" \
  -d '{
    "text": "próxima reunião sobre IA na saúde, 45 minutos",
    "org": "org_demo"
  }'
```

### Teste Unitário

```python
import pytest
from agent.integrations.deepresearch_client import DeepResearchClient

def test_client_health_check():
    client = DeepResearchClient("http://localhost:8000")
    assert client.health_check() == True

def test_research_sync():
    client = DeepResearchClient("http://localhost:8000")
    result = client.research_sync("Test Topic", max_steps=3)
    
    assert 'report' in result
    assert 'avg_quality' in result
    assert result['avg_quality'] >= 0
    assert result['avg_quality'] <= 10

def test_circuit_breaker():
    # Simulate failures
    client = DeepResearchClient("http://invalid-url:9999")
    
    # Should open circuit after 5 failures
    for _ in range(10):
        try:
            client.research_sync("test")
        except:
            pass
    
    assert client._circuit_open == True
```

## 📈 Performance

### Benchmarks

| Cenário | Tempo Médio | Qualidade |
|---------|-------------|-----------|
| Pesquisa Básica (Meeting Agent) | 2-5s | 5.0/10 |
| Deep Research (3 steps) | 30-60s | 7.5/10 |
| Deep Research (5 steps) | 60-180s | 8.5/10 |
| Deep Research (10 steps) | 180-300s | 9.2/10 |

### Otimizações

1. **Cache**: Deep Research Agent cacheia resultados por 1 hora
2. **Async Mode**: Use para pesquisas longas (não bloqueia HTTP)
3. **Max Steps**: Ajuste baseado em urgência (3 steps = rápido, 10 = profundo)
4. **Whitelist**: Habilite apenas para orgs que realmente precisam

## 🚨 Troubleshooting

### Deep Research não responde

```bash
# 1. Check if service is running
curl http://localhost:8000/health

# 2. Check logs
tail -f logs/deepresearch.log

# 3. Check environment variables
echo $DEEPRESEARCH_API_URL
echo $DEEPRESEARCH_ENABLED
```

### Circuit breaker aberto

```python
# Reset circuit breaker
client._circuit_open = False
client._failure_count = 0
```

### Timeout frequente

```bash
# Increase timeout
export DEEPRESEARCH_TIMEOUT=600  # 10 minutes

# Or reduce max steps
export DEEPRESEARCH_MAX_STEPS=3
```

## 🔐 Segurança

### Autenticação (Opcional)

```bash
# Deep Research Agent
export API_KEY=super-secret-key
export REQUIRE_API_KEY=true

# Meeting Agent
export DEEPRESEARCH_API_KEY=super-secret-key
```

### Network Isolation (Azure)

```bash
# Deploy Deep Research com ingress interno
az containerapp create \
  --ingress internal \
  ...

# Apenas Meeting Agent tem acesso
```

## 📚 Referências

- [Deep Research Agent API Docs](http://localhost:8000/docs)
- [Meeting Agent Architecture](./ARCHITECTURE.md)
- [Azure Container Apps Networking](https://learn.microsoft.com/azure/container-apps/networking)

---

**Última atualização**: 2025-10-23  
**Versão**: 1.0.0
