"""
Debug do Deep Research Agent no Azure

Investiga por que está retornando quality=0.0 e steps=0.

Testes:
1. Health check detalhado
2. Teste de research simples
3. Verificação de API keys
4. Análise de response completa
5. Teste com diferentes providers
"""

import sys
import os
import json
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from datetime import datetime


AZURE_URL = "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"


def print_section(title):
    """Print section header."""
    print("\n" + "="*80)
    print(f"🔍 {title}")
    print("="*80 + "\n")


def test_health_detailed():
    """Teste detalhado de health check."""
    print_section("TESTE 1: HEALTH CHECK DETALHADO")
    
    try:
        client = httpx.Client(timeout=30.0, http2=True)
        
        print("📡 Enviando GET /health...")
        start = time.time()
        response = client.get(f"{AZURE_URL}/health")
        elapsed = time.time() - start
        
        print(f"⏱️  Tempo de resposta: {elapsed:.2f}s")
        print(f"📊 Status Code: {response.status_code}")
        print(f"🔖 Headers:")
        for key, value in response.headers.items():
            print(f"   {key}: {value}")
        
        print(f"\n📄 Body:")
        try:
            data = response.json()
            print(json.dumps(data, indent=2))
        except:
            print(response.text)
        
        if response.status_code == 200:
            print("\n✅ Health check OK")
            return True
        else:
            print(f"\n❌ Health check falhou: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_simple_research():
    """Teste de research mais simples possível."""
    print_section("TESTE 2: RESEARCH SIMPLES")
    
    try:
        client = httpx.Client(timeout=600.0, http2=True)
        
        payload = {
            "topic": "Python programming",
            "model_provider": "openai",
            "max_steps": 2,
            "search_provider": "tavily",
            "correlation_id": "debug-test-001"
        }
        
        print(f"📤 Request payload:")
        print(json.dumps(payload, indent=2))
        
        print(f"\n📡 Enviando POST /research...")
        start = time.time()
        
        response = client.post(
            f"{AZURE_URL}/research",
            json=payload
        )
        
        elapsed = time.time() - start
        
        print(f"\n⏱️  Tempo de resposta: {elapsed:.2f}s")
        print(f"📊 Status Code: {response.status_code}")
        
        print(f"\n📄 Response Body:")
        try:
            data = response.json()
            print(json.dumps(data, indent=2))
            
            # Análise detalhada
            print(f"\n📊 ANÁLISE:")
            print(f"   Quality: {data.get('avg_quality', 'N/A')}")
            print(f"   Steps completed: {data.get('steps_completed', 'N/A')}")
            print(f"   Total time: {data.get('total_time_seconds', 'N/A')}s")
            print(f"   Report length: {len(data.get('report', ''))} chars")
            print(f"   Search steps: {len(data.get('search_steps', []))}")
            
            if data.get('avg_quality', 0) == 0:
                print(f"\n⚠️  PROBLEMA IDENTIFICADO: Quality = 0")
                print(f"   Possíveis causas:")
                print(f"   - API keys inválidas")
                print(f"   - Rate limiting")
                print(f"   - Erro interno do Agent")
                
                # Check error field
                if 'error' in data:
                    print(f"\n❌ Error no response: {data['error']}")
                
                # Check search steps for errors
                if data.get('search_steps'):
                    print(f"\n🔍 Analisando search steps:")
                    for i, step in enumerate(data['search_steps']):
                        print(f"\n   Step {i+1}:")
                        print(f"      Status: {step.get('status', 'N/A')}")
                        if step.get('error'):
                            print(f"      ❌ Error: {step['error']}")
            else:
                print(f"\n✅ Research completou com sucesso")
            
            return data
            
        except Exception as e:
            print(f"❌ Erro ao parsear response: {e}")
            print(f"Raw response: {response.text[:500]}")
            return None
            
    except httpx.TimeoutException:
        print(f"\n❌ TIMEOUT após {elapsed:.2f}s")
        return None
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_env_check():
    """Verifica variáveis de ambiente."""
    print_section("TESTE 3: VERIFICAÇÃO DE VARIÁVEIS DE AMBIENTE")
    
    from dotenv import load_dotenv
    
    # Load .env
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ .env carregado: {env_path}")
    else:
        print(f"❌ .env não encontrado: {env_path}")
        return False
    
    # Check critical env vars
    env_vars = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "DEEPRESEARCH_API_URL": os.getenv("DEEPRESEARCH_API_URL"),
        "MODEL_PROVIDER": os.getenv("MODEL_PROVIDER"),
    }
    
    print("\n📋 Variáveis de ambiente:")
    for key, value in env_vars.items():
        if value:
            # Mask sensitive data
            if "KEY" in key and len(value) > 10:
                masked = value[:10] + "..." + value[-4:]
            else:
                masked = value
            print(f"   ✅ {key}: {masked}")
        else:
            print(f"   ❌ {key}: NOT SET")
    
    return all(v for k, v in env_vars.items() if k != "DEEPRESEARCH_API_URL")


def test_direct_azure_api():
    """Testa chamada direta à API do Azure (sem client)."""
    print_section("TESTE 4: CHAMADA DIRETA À API AZURE")
    
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path)
        
        # Create minimal request
        client = httpx.Client(timeout=600.0, http2=True)
        
        payload = {
            "topic": "AI trends 2025",
            "model_provider": "openai",
            "max_steps": 1,  # Mínimo possível
            "search_provider": "tavily"
        }
        
        print(f"📤 Payload (1 step apenas):")
        print(json.dumps(payload, indent=2))
        
        print(f"\n📡 POST {AZURE_URL}/research")
        print(f"⏱️  Aguardando resposta (timeout 600s)...")
        
        start = time.time()
        response = client.post(f"{AZURE_URL}/research", json=payload)
        elapsed = time.time() - start
        
        print(f"\n⏱️  Completou em {elapsed:.2f}s")
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ RESPOSTA RECEBIDA")
            print(f"   Steps: {data.get('steps_completed', 0)}")
            print(f"   Quality: {data.get('avg_quality', 0)}")
            print(f"   Time: {data.get('total_time_seconds', 0)}s")
            
            # Check for actual content
            if data.get('report'):
                print(f"   Report: {len(data['report'])} chars")
                print(f"\n📄 Primeiros 200 chars do report:")
                print(f"   {data['report'][:200]}...")
            else:
                print(f"   ❌ Report vazio!")
            
            if data.get('search_steps'):
                print(f"\n🔍 Search steps ({len(data['search_steps'])}):")
                for i, step in enumerate(data['search_steps']):
                    print(f"   Step {i+1}:")
                    print(f"      Query: {step.get('query', 'N/A')[:50]}...")
                    print(f"      Results: {step.get('results_count', 0)}")
                    if step.get('error'):
                        print(f"      ❌ Error: {step['error']}")
            
            return data
        else:
            print(f"\n❌ Erro {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_azure_logs():
    """Simula verificação de logs do Azure."""
    print_section("TESTE 5: VERIFICAÇÃO DE LOGS AZURE")
    
    print("📋 Para verificar logs do Azure Container Apps:")
    print()
    print("   1. Via Azure Portal:")
    print("      - Container Apps > deepresearch-agent > Monitoring > Log stream")
    print()
    print("   2. Via Azure CLI:")
    print("      az containerapp logs show \\")
    print("        --name deepresearch-agent \\")
    print("        --resource-group TK_Technologies \\")
    print("        --follow")
    print()
    print("   3. Verificar Application Insights:")
    print("      - Buscar por correlation_id: 'debug-test-001'")
    print()
    print("   4. Comandos úteis:")
    print("      # Ver últimas 100 linhas")
    print("      az containerapp logs show -n deepresearch-agent -g TK_Technologies --tail 100")
    print()
    print("      # Filtrar por erro")
    print("      az containerapp logs show -n deepresearch-agent -g TK_Technologies | grep -i error")
    print()


def test_api_keys_validation():
    """Testa se as API keys estão válidas."""
    print_section("TESTE 6: VALIDAÇÃO DE API KEYS")
    
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    
    # Test OpenAI
    print("🔑 Testando OpenAI API Key...")
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            client = httpx.Client(timeout=10.0)
            response = client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {openai_key}"}
            )
            if response.status_code == 200:
                print(f"   ✅ OpenAI key válida")
            else:
                print(f"   ❌ OpenAI key inválida: {response.status_code}")
                print(f"      {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Erro ao testar OpenAI: {e}")
    else:
        print(f"   ⚠️  OpenAI key não configurada")
    
    # Test Tavily
    print("\n🔍 Testando Tavily API Key...")
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            client = httpx.Client(timeout=10.0)
            response = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": "test",
                    "max_results": 1
                }
            )
            if response.status_code == 200:
                print(f"   ✅ Tavily key válida")
            else:
                print(f"   ❌ Tavily key inválida: {response.status_code}")
                print(f"      {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Erro ao testar Tavily: {e}")
    else:
        print(f"   ⚠️  Tavily key não configurada")


def main():
    """Executa todos os testes de debug."""
    print("\n" + "="*80)
    print("🚀 DEBUG DO AZURE DEEP RESEARCH AGENT")
    print("="*80)
    print(f"\nURL: {AZURE_URL}")
    print(f"Data/Hora: {datetime.now().isoformat()}")
    
    results = {}
    
    # Teste 1: Health check
    results['health'] = test_health_detailed()
    
    if not results['health']:
        print("\n⚠️  Health check falhou - Azure pode estar offline")
        print("   Continuando com outros testes...")
    
    # Teste 2: Environment
    results['env'] = test_env_check()
    
    # Teste 3: API Keys
    test_api_keys_validation()
    
    # Teste 4: Simple research
    results['simple_research'] = test_simple_research()
    
    # Teste 5: Direct API call
    results['direct_api'] = test_direct_azure_api()
    
    # Teste 6: Azure logs info
    test_azure_logs()
    
    # Summary
    print("\n" + "="*80)
    print("📊 RESUMO DO DEBUG")
    print("="*80 + "\n")
    
    if results.get('health'):
        print("✅ Azure está online e respondendo")
    else:
        print("❌ Azure não está respondendo ao health check")
    
    if results.get('env'):
        print("✅ Variáveis de ambiente configuradas")
    else:
        print("❌ Faltam variáveis de ambiente")
    
    if results.get('simple_research'):
        quality = results['simple_research'].get('avg_quality', 0)
        if quality > 0:
            print(f"✅ Research funcionando (quality: {quality})")
        else:
            print(f"⚠️  Research retorna quality 0")
            print(f"   CAUSA PROVÁVEL:")
            
            # Analyze the response
            if not results['simple_research'].get('search_steps'):
                print(f"   - Nenhum search step executado")
                print(f"   - Problema com Tavily API ou configuração")
            elif not results['simple_research'].get('report'):
                print(f"   - Search executou mas não gerou report")
                print(f"   - Problema com LLM (OpenAI/Gemini/Claude)")
            else:
                print(f"   - Causa desconhecida - verificar logs do Azure")
    
    print("\n" + "="*80)
    print("🎯 PRÓXIMOS PASSOS RECOMENDADOS")
    print("="*80 + "\n")
    
    print("1. Verificar logs do Azure Container Apps:")
    print("   az containerapp logs show -n deepresearch-agent -g TK_Technologies --tail 100")
    print()
    print("2. Verificar se API keys estão configuradas no Azure:")
    print("   az containerapp show -n deepresearch-agent -g TK_Technologies --query properties.configuration.secrets")
    print()
    print("3. Testar localmente o Deep Research Agent:")
    print("   cd deepresearch-agent")
    print("   python -m uvicorn api.main:app --reload")
    print()
    print("4. Se quality=0 persistir, verificar:")
    print("   - Rate limits da OpenAI")
    print("   - Créditos da Tavily")
    print("   - Logs de erro no Azure")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
