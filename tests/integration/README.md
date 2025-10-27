# Node.js Integration Tests

Testes de integração para **Meeting Agent + Deep Research Agent**.

---

## 🚀 Quick Start

### Instalação

```bash
npm install
```

### Executar Todos os Testes

```bash
npm test
```

---

## 🧪 Testes Disponíveis

### 1. Health Checks (~5s)

```bash
npm run test:health
```

**Verifica:**
- ✅ Deep Research Agent responde em `http://localhost:8000/health`
- ✅ Meeting Agent responde em `http://localhost:8001/health`

### 2. Deep Research Standalone (~2 min)

```bash
npm run test:deepresearch
```

**Executa:**
- 🔍 Pesquisa: "AI integration best practices 2025"
- 📊 Configuração: 3 steps, model=openai
- ✅ Validação: quality_score ≥ 3.0

**Output esperado:**
```
✅ Pesquisa concluída!
   Duration: 120.5s
   Steps: 3
   Quality: 4.2/10
   Model: gpt-5
```

### 3. Meeting Agent Quick (~10s)

```bash
npm run test:meeting
```

**Executa:**
- 📅 Query: "Create a quick team sync meeting"
- ⚡ Rápido: não aciona Deep Research
- ✅ Validação: meeting criado com facts de MongoDB/Semantic/FTS

**Output esperado:**
```
✅ Meeting criado!
   Duration: 8.3s
   Meeting ID: mtg_XXXX
   Facts used: 3
   Deep Research used: false
```

### 4. Integração Completa (~4 min)

```bash
npm run test:integration
```

**Executa:**
- 🔗 Query complexa: "AI transformation and digital innovation roadmap 2025"
- 🧠 Aciona Deep Research (< 8 facts encontrados)
- 📊 Deep Research: 5 steps, ~200s
- ✅ Validação: quality ≥ 4.0, meeting com agenda completa

**Output esperado:**
```
✅ Meeting com Deep Research criado!
   Duration: 205.3s
   Meeting ID: mtg_XXXX
   Facts used: 5
   Deep Research used: true
   Deep Research quality: 4.5
   Agenda title: AI Transformation and Digital Innovation Roadmap 2025
   Agenda sections: 8
```

---

## ⚙️ Configuração

### Environment Variables

```bash
# Opcional - padrão: localhost
export DEEPRESEARCH_URL=http://localhost:8000
export MEETING_AGENT_URL=http://localhost:8001
```

### Pré-requisitos

**Servidores rodando:**

```bash
# Terminal 1 - Deep Research Agent
cd deepresearch-agent
.\venv\Scripts\Activate.ps1
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Meeting Agent
cd meeting-agent-main
.\venv\Scripts\Activate.ps1
uvicorn agent.api:app --reload --host 0.0.0.0 --port 8001
```

---

## 📊 Métricas Esperadas

| Teste | Duração | Quality Score | Success Rate |
|-------|---------|---------------|--------------|
| Health Checks | ~5s | N/A | 100% |
| Deep Research (3 steps) | ~120-180s | ≥ 3.0 | ≥ 90% |
| Meeting Quick | ~5-10s | N/A | ≥ 95% |
| Integration (5 steps) | ~180-240s | ≥ 4.0 | ≥ 80% |

---

## 🔧 Troubleshooting

### Erro: ECONNREFUSED

```
Error: connect ECONNREFUSED 127.0.0.1:8000
```

**Solução:** Iniciar servidor Deep Research:
```bash
cd deepresearch-agent
uvicorn api.main:app --reload --port 8000
```

### Erro: Timeout

```
Error: timeout of 180000ms exceeded
```

**Solução 1:** Reduzir `max_steps` no teste:
```javascript
max_steps: 3  // ao invés de 5
```

**Solução 2:** Aumentar timeout no código:
```javascript
timeout: 300000  // 5 minutos
```

### Erro: Module not found

```
Error: Cannot find module 'axios'
```

**Solução:**
```bash
npm install axios
```

---

## 📁 Estrutura

```
tests/integration/
├── node-client.js                  # Testes principais
├── deepresearch-integration.js     # Clientes para orquestrador
├── package.json                    # Dependências e scripts
└── README.md                       # Este arquivo
```

---

## 🔗 Integração com chat-agent-main

Para usar no orquestrador `chat-agent-main`:

```javascript
const { MeetingAgentClient } = require('./deepresearch-integration');

const meetingClient = new MeetingAgentClient('http://localhost:8001');

// Health check
const health = await meetingClient.healthCheck();

// Criar meeting
const result = await meetingClient.createMeeting(
  'Create AI strategy meeting',
  {
    orgId: 'org_123',
    userId: 'user_456',
    language: 'en'
  }
);

if (result.success) {
  console.log('Meeting created:', result.meeting_id);
  console.log('Deep Research used:', result.deep_research_used);
}
```

Ver exemplo completo em: `deepresearch-integration.js`

---

## 📚 Documentação

- [TEST_INTEGRATION_GUIDE.md](../../TEST_INTEGRATION_GUIDE.md) - Guia completo
- [RELEASE_NOTES.md](../../RELEASE_NOTES.md) - Release notes v1.0.0
- [DEPLOY_GUIDE.md](../../meeting-agent-main/docs/DEPLOY_GUIDE.md) - Deploy Azure

---

**Version:** 1.0.0  
**Last Updated:** October 24, 2025
