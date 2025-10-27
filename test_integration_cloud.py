"""
Teste de integração DeepResearch + Meeting Agent na nuvem Azure
Executa: python test_integration_cloud.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Adicionar path do meeting-agent
sys.path.insert(0, str(Path(__file__).parent))

from agent.integrations.deepresearch_client import DeepResearchClient

async def test_cloud_integration():
    # URL do Azure já configurada no .env
    base_url = os.getenv(
        "DEEPRESEARCH_API_URL",
        "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
    )
    
    print(f"🌐 Conectando ao DeepResearch: {base_url}")
    client = DeepResearchClient(base_url=base_url, timeout=300)
    
    # Teste 1: Health Check
    print("\n" + "="*80)
    print("TESTE 1: HEALTH CHECK")
    print("="*80)
    try:
        health = await client.health_check()
        print(f"✅ Status: {health.get('status')}")
        print(f"✅ Version: {health.get('version')}")
        print(f"✅ Model Provider: {health.get('model_provider')}")
        print(f"✅ Search Provider: {health.get('search_provider')}")
        
        # Validações críticas
        assert health.get('status') == 'healthy', "Status não é healthy!"
        assert health.get('version') == '2.1.0', "Versão incorreta!"
        assert health.get('model_provider') == 'openai', "Model provider não é openai!"
        
    except Exception as e:
        print(f"❌ FALHA: {e}")
        return False
    
    # Teste 2: Pesquisa Síncrona
    print("\n" + "="*80)
    print("TESTE 2: PESQUISA SÍNCRONA")
    print("="*80)
    query = "What are the latest AI agent frameworks in 2025?"
    print(f"📝 Query: {query}")
    
    try:
        result = await client.research_sync(
            query=query,
            model_provider="openai",
            max_steps=3,
            search_provider="tavily"
        )
        
        print(f"✅ Pesquisa concluída!")
        print(f"📊 Passos executados: {result['metadata']['steps_taken']}")
        print(f"🤖 Modelo: {result['metadata']['model_provider']}")
        print(f"🔍 Provider: {result['metadata']['search_provider']}")
        print(f"⏱️  Tempo: {result['metadata']['total_time_seconds']:.2f}s")
        print(f"📚 Fontes: {len(result.get('sources', []))}")
        
        # Validações críticas
        assert result['metadata']['model_provider'] == 'openai', "Model provider incorreto!"
        assert result['metadata']['search_provider'] == 'tavily', "Search provider incorreto!"
        assert len(result.get('report', '')) > 100, "Report muito curto!"
        assert len(result.get('sources', [])) > 0, "Sem fontes!"
        
        print("\n📝 PREVIEW DO REPORT (primeiras 500 chars):")
        print("-" * 80)
        print(result['report'][:500] + "...")
        print("-" * 80)
        
        print("\n📚 FONTES:")
        for idx, source in enumerate(result.get('sources', [])[:5], 1):
            print(f"  {idx}. {source}")
        
        print("\n✅ TODOS OS TESTES PASSARAM!")
        return True
        
    except Exception as e:
        print(f"❌ FALHA: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 TESTE DE INTEGRAÇÃO NA NUVEM AZURE")
    print("="*80)
    print("")
    
    success = asyncio.run(test_cloud_integration())
    
    print("\n" + "="*80)
    if success:
        print("✅ INTEGRAÇÃO FUNCIONANDO CORRETAMENTE!")
        print("="*80)
        exit(0)
    else:
        print("❌ INTEGRAÇÃO COM PROBLEMAS - VERIFICAR LOGS")
        print("="*80)
        exit(1)
