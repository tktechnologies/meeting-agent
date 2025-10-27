"""
Teste END-TO-END: Meeting Agent chama DeepResearch na nuvem
Simula o fluxo completo de uma pergunta do usuário até a resposta final
Executa: python test_e2e_cloud.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Adicionar path do meeting-agent
sys.path.insert(0, str(Path(__file__).parent))

from agent.integrations.deepresearch_client import (
    DeepResearchClient,
    DeepResearchError,
    DeepResearchTimeoutError
)

async def test_e2e_meeting_to_deepresearch():
    """
    Simula fluxo real: Meeting Agent precisa de pesquisa profunda
    """
    print("🎯 TESTE END-TO-END: Meeting Agent → DeepResearch Agent")
    print("="*80)
    
    # Cenário: Usuário faz pergunta complexa no Meeting Agent
    user_query = "Como implementar RAG em sistemas de IA corporativos?"
    
    print(f"\n👤 USUÁRIO PERGUNTA: '{user_query}'")
    print("\n🤖 Meeting Agent identifica: precisa de pesquisa profunda")
    print("📡 Meeting Agent chama DeepResearch Agent na nuvem...")
    
    # Inicializar cliente (usa DEEPRESEARCH_API_URL do .env)
    client = DeepResearchClient()
    
    try:
        # Verificar disponibilidade
        print("\n1️⃣ Verificando disponibilidade do DeepResearch...")
        health = await client.health_check()
        print(f"   ✅ DeepResearch disponível (v{health.get('version')})")
        print(f"   ✅ Model Provider: {health.get('model_provider')}")
        
        # Fazer pesquisa
        print("\n2️⃣ Executando pesquisa profunda...")
        print(f"   🔍 Provider: OpenAI GPT-5")
        print(f"   📊 Max steps: 5")
        
        result = await client.research_sync(
            query=user_query,
            model_provider="openai",
            max_steps=5,
            search_provider="tavily"
        )
        
        print(f"\n3️⃣ Pesquisa concluída!")
        print(f"   ⏱️  Tempo total: {result['metadata']['total_time_seconds']:.1f}s")
        print(f"   📊 Passos executados: {result['metadata']['steps_taken']}")
        print(f"   📚 Fontes coletadas: {len(result.get('sources', []))}")
        print(f"   ⭐ Qualidade: {result['metadata']['final_quality_score']}/10")
        
        # Processar resultados
        print("\n4️⃣ Meeting Agent processa resultados...")
        report = result.get('report', '')
        sources = result.get('sources', [])
        
        # Simular criação de fatos estruturados
        facts = []
        for idx, source in enumerate(sources[:10], 1):
            fact = {
                "content": f"Informação relevante sobre RAG da fonte {idx}",
                "source": source,
                "confidence": 0.9,
                "_deepresearch_priority": True,
                "_from_deepresearch": True
            }
            facts.append(fact)
        
        print(f"   ✅ Criados {len(facts)} fatos estruturados")
        
        # Simular resposta final
        print("\n5️⃣ Meeting Agent gera resposta final...")
        final_response = {
            "answer": f"Com base em pesquisa profunda: {report[:200]}...",
            "sources": sources[:5],
            "research_metadata": result['metadata'],
            "structured_facts": facts
        }
        
        print("\n" + "="*80)
        print("✅ TESTE E2E COMPLETO!")
        print("="*80)
        print(f"\n📊 MÉTRICAS:")
        print(f"   • Tempo de resposta: {result['metadata']['total_time_seconds']:.1f}s")
        print(f"   • Qualidade: {result['metadata']['final_quality_score']}/10")
        print(f"   • Fontes: {len(sources)}")
        print(f"   • Fatos criados: {len(facts)}")
        
        print(f"\n📝 RESPOSTA FINAL (preview):")
        print("-" * 80)
        print(final_response['answer'])
        print("-" * 80)
        
        print(f"\n📚 TOP 5 FONTES:")
        for idx, source in enumerate(sources[:5], 1):
            print(f"   {idx}. {source}")
        
        # Validações
        assert result['metadata']['model_provider'] == 'openai', "❌ Model provider incorreto"
        assert result['metadata']['steps_taken'] > 0, "❌ Nenhum passo executado"
        assert len(report) > 500, "❌ Report muito curto"
        assert len(sources) > 0, "❌ Sem fontes"
        assert len(facts) > 0, "❌ Sem fatos estruturados"
        
        print("\n✅ TODAS AS VALIDAÇÕES PASSARAM!")
        return True
        
    except DeepResearchTimeoutError as e:
        print(f"\n⏱️  TIMEOUT: {e}")
        print("💡 Considere aumentar DEEPRESEARCH_TIMEOUT no .env")
        return False
        
    except DeepResearchError as e:
        print(f"\n❌ ERRO NA PESQUISA: {e}")
        return False
        
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 TESTE E2E - INTEGRAÇÃO COMPLETA")
    print("="*80)
    print("")
    
    success = asyncio.run(test_e2e_meeting_to_deepresearch())
    
    print("\n" + "="*80)
    if success:
        print("✅ FLUXO E2E FUNCIONANDO!")
        print("📌 Meeting Agent → DeepResearch → Resposta = OK")
        print("="*80)
        exit(0)
    else:
        print("❌ FLUXO E2E COM PROBLEMAS")
        print("="*80)
        exit(1)
