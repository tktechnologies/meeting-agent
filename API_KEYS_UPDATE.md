# 🔑 API Keys & Models - Update Guide

## ✅ O QUE FOI ATUALIZADO

O **Meeting Agent** foi atualizado para usar as **mesmas especificações** do **Deep Research Agent**, incluindo suporte para 3 providers de IA e modelos mais recentes.

---

## 📊 MUDANÇAS REALIZADAS

### **1. Modelos de IA Atualizados**

| Modelo | Antes (❌) | Depois (✅) |
|--------|-----------|------------|
| **OpenAI** | `gpt-4o` | `gpt-5` |
| **Gemini** | `gemini-2.0-flash-exp` | `gemini-2.5-pro` |
| **Anthropic** | Não disponível | `claude-sonnet-4-5` |

### **2. Novas Variáveis de Ambiente**

Adicionadas ao `.env.example`:

```bash
# AI Model Configuration
MODEL_PROVIDER=openai  # openai, gemini, or anthropic

# OpenAI (GPT-5)
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL_NAME=gpt-5

# Google Gemini (Gemini 2.5 Pro)
GOOGLE_API_KEY=your-google-api-key-here
GEMINI_MODEL_NAME=gemini-2.5-pro

# Anthropic Claude (Claude Sonnet 4-5)
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ANTHROPIC_MODEL_NAME=claude-sonnet-4-5

# Model Settings
TEMPERATURE=0.7
MAX_TOKENS=4000
```

### **3. Deep Research Configuration Atualizada**

```bash
# Deep Research sempre usa Tavily
DEEPRESEARCH_SEARCH_PROVIDER=tavily

# URL do Azure atualizada
DEEPRESEARCH_API_URL=https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io

# Provider padrão: OpenAI (GPT-5)
DEEPRESEARCH_MODEL=openai

# Para reuniões: pesquisa profunda com 10 steps
DEEPRESEARCH_MAX_STEPS=10

# Persistir resultados no MongoDB
DEEPRESEARCH_PERSIST_RESULTS=true
```

---

## 🔧 COMO ATUALIZAR SEU .ENV

### **Passo 1: Adicionar Novas API Keys**

Se você ainda não tem, obtenha as API keys:

1. **OpenAI GPT-5**: https://platform.openai.com/api-keys
2. **Google Gemini**: https://aistudio.google.com/app/apikey
3. **Anthropic Claude**: https://console.anthropic.com/

### **Passo 2: Atualizar .env**

Copie as seções atualizadas do `.env.example` para seu `.env`:

```bash
# Copiar configurações de modelo
MODEL_PROVIDER=openai

# Suas API keys reais
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...

# Modelos (pode manter os padrões)
OPENAI_MODEL_NAME=gpt-5
GEMINI_MODEL_NAME=gemini-2.5-pro
ANTHROPIC_MODEL_NAME=claude-sonnet-4-5
```

### **Passo 3: Atualizar Deep Research Config**

```bash
DEEPRESEARCH_ENABLED=true
DEEPRESEARCH_API_URL=https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io
DEEPRESEARCH_MODEL=openai
DEEPRESEARCH_SEARCH_PROVIDER=tavily
DEEPRESEARCH_MAX_STEPS=10
DEEPRESEARCH_PERSIST_RESULTS=true
```

---

## 🎯 SELEÇÃO DE PROVIDER

O Meeting Agent agora suporta 3 providers de IA. Escolha baseado em suas necessidades:

### **OpenAI GPT-5** (Padrão - Recomendado)
```bash
MODEL_PROVIDER=openai
DEEPRESEARCH_MODEL=openai
```
- ✅ **Melhor qualidade** de resposta
- ✅ Excelente para análise de reuniões
- ⚠️ Custo: $$$

### **Google Gemini 2.5 Pro**
```bash
MODEL_PROVIDER=gemini
DEEPRESEARCH_MODEL=gemini
```
- ✅ **Rápido** e eficiente
- ✅ Bom custo-benefício
- ✅ Excelente para pesquisas web
- ⚠️ Custo: $$

### **Anthropic Claude Sonnet 4-5**
```bash
MODEL_PROVIDER=anthropic
DEEPRESEARCH_MODEL=anthropic
```
- ✅ **Equilíbrio** qualidade/custo
- ✅ Excelente para textos longos
- ✅ Análise detalhada
- ⚠️ Custo: $$

---

## 📋 COMPATIBILIDADE

### **Código Atualizado**

Os seguintes arquivos foram atualizados:

- ✅ `.env.example` - Novas variáveis de ambiente
- ✅ `agent/config.py` - Suporte para 3 providers
- ✅ Deep Research integration - URLs e defaults atualizados

### **Retrocompatibilidade**

✅ Se você **não adicionar** as novas API keys, o sistema continuará funcionando com OpenAI (padrão).

⚠️ **Ação necessária**: Se você quiser usar Gemini ou Anthropic, **DEVE** adicionar as respectivas API keys no `.env`.

---

## 🧪 TESTAR CONFIGURAÇÃO

Após atualizar seu `.env`, teste:

```bash
# Verificar se configurações foram carregadas
python -c "from agent.config import *; print(f'Provider: {MODEL_PROVIDER}'); print(f'OpenAI: {OPENAI_MODEL_NAME}'); print(f'Gemini: {GEMINI_MODEL_NAME}'); print(f'Anthropic: {ANTHROPIC_MODEL_NAME}')"
```

**Saída esperada:**
```
Provider: openai
OpenAI: gpt-5
Gemini: gemini-2.5-pro
Anthropic: claude-sonnet-4.5
```

---

## 🚨 TROUBLESHOOTING

### Erro: "OPENAI_API_KEY is required"
**Solução**: Adicione `OPENAI_API_KEY=sk-...` no `.env`

### Erro: "MODEL_PROVIDER must be one of: openai, gemini, anthropic"
**Solução**: Verifique se `MODEL_PROVIDER` no `.env` está correto (lowercase)

### Erro: "GOOGLE_API_KEY is required when MODEL_PROVIDER=gemini"
**Solução**: Se usar Gemini, adicione `GOOGLE_API_KEY=AIza...` no `.env`

### Erro: "ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic"
**Solução**: Se usar Claude, adicione `ANTHROPIC_API_KEY=sk-ant-...` no `.env`

---

## 📞 SUPORTE

Se encontrar problemas:

1. Verifique se `.env` está atualizado com as novas variáveis
2. Confirme que as API keys são válidas
3. Teste com `python -c "from agent.config import *; print(MODEL_PROVIDER)"`
4. Consulte logs em `logs/app.log`

---

**Última atualização**: 2025-10-24  
**Versão**: 2.0.0
