"""
Teste de stress: múltiplas requisições simultâneas
Executa: python test_stress_cloud.py
"""
import asyncio
import time
import sys
from pathlib import Path

# Adicionar path do meeting-agent
sys.path.insert(0, str(Path(__file__).parent))

from agent.integrations.deepresearch_client import DeepResearchClient

async def single_request(client, query_id, query):
    """Faz uma requisição"""
    start = time.time()
    try:
        result = await client.research_sync(
            query=query,
            model_provider="openai",
            max_steps=2,  # Reduzido para ser mais rápido
            search_provider="tavily"
        )
        elapsed = time.time() - start
        print(f"✅ Request {query_id}: OK em {elapsed:.1f}s")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ Request {query_id}: FALHOU em {elapsed:.1f}s - {str(e)[:50]}")
        return False

async def test_concurrent_requests():
    """Testa 5 requisições simultâneas"""
    print("🔥 TESTE DE STRESS: 5 requisições simultâneas")
    print("="*80)
    print("Isso simula múltiplos usuários fazendo perguntas ao mesmo tempo")
    print("")
    
    client = DeepResearchClient(timeout=180)  # 3 minutos por requisição
    
    queries = [
        "What is machine learning?",
        "Explain neural networks",
        "What are transformers in AI?",
        "How does RAG work?",
        "What is vector database?"
    ]
    
    print(f"📊 Executando {len(queries)} requisições simultâneas...")
    print("")
    
    start_time = time.time()
    
    # Executar todas simultaneamente
    tasks = [
        single_request(client, i+1, query)
        for i, query in enumerate(queries)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r is True)
    
    print("\n" + "="*80)
    print("📊 RESULTADOS DO STRESS TEST")
    print("="*80)
    print(f"✅ Sucesso: {success_count}/5")
    print(f"❌ Falhas: {5 - success_count}/5")
    print(f"⏱️  Tempo total: {elapsed:.1f}s")
    print(f"📈 Taxa de sucesso: {(success_count/5)*100:.0f}%")
    
    # Análise
    print("\n📊 ANÁLISE:")
    if success_count == 5:
        print("   🟢 EXCELENTE: Sistema suporta carga concorrente")
    elif success_count >= 4:
        print("   🟡 BOM: Sistema funciona com pequenos problemas")
    elif success_count >= 3:
        print("   🟠 ATENÇÃO: Sistema com problemas de carga")
    else:
        print("   🔴 CRÍTICO: Sistema não suporta carga concorrente")
    
    return success_count >= 4  # Pelo menos 80% de sucesso

if __name__ == "__main__":
    print("🚀 TESTE DE STRESS")
    print("="*80)
    print("")
    
    success = asyncio.run(test_concurrent_requests())
    
    print("\n" + "="*80)
    if success:
        print("✅ SISTEMA SUPORTA CARGA CONCORRENTE")
        print("="*80)
        exit(0)
    else:
        print("❌ SISTEMA COM PROBLEMAS DE CARGA")
        print("💡 Considere aumentar recursos no Azure")
        print("="*80)
        exit(1)
