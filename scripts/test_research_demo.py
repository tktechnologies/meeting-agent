"""
Teste de pesquisa real com Deep Research Agent
Mostra resultado completo formatado no terminal
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from agent.integrations.deepresearch_client import DeepResearchClient
from agent.integrations.research_converter import convert_research_to_facts, validate_research_result


def print_separator(char='=', length=80):
    print(char * length)


def format_quality_bar(quality: float, max_score: float = 10.0) -> str:
    """Create visual quality bar"""
    filled = int((quality / max_score) * 20)
    empty = 20 - filled
    bar = '█' * filled + '░' * empty
    return f"[{bar}] {quality:.1f}/{max_score}"


def test_research_full():
    """Execute a full research and display formatted results"""
    
    base_url = os.environ.get(
        "DEEPRESEARCH_BASE_URL",
        "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
    )
    
    print("\n")
    print_separator('━')
    print("🔬 TESTE DE PESQUISA DEEP RESEARCH AGENT")
    print_separator('━')
    print()
    
    # Initialize client
    client = DeepResearchClient(base_url=base_url)
    print(f"🌐 Conectado a: {base_url}")
    print()
    
    # Research query
    query = "Quais são as melhores práticas para integração de agentes de IA em sistemas empresariais em 2025?"
    
    print(f"❓ Pergunta de Pesquisa:")
    print(f"   {query}")
    print()
    
    print("⏳ Iniciando pesquisa profunda...")
    print("   (Isso pode levar 1-3 minutos dependendo da complexidade)")
    print()
    
    start_time = datetime.now()
    
    # Execute research
    result = client.research_sync(
        topic=query,
        model_provider="openai",
        max_steps=5,  # 5 steps for more comprehensive results
        correlation_id="test-demo-research"
    )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print()
    print_separator('─')
    print("✅ PESQUISA CONCLUÍDA!")
    print_separator('─')
    print()
    
    # Display metrics
    print("📊 MÉTRICAS DA PESQUISA:")
    print(f"   ⏱️  Tempo de execução: {duration:.1f}s ({duration/60:.1f} minutos)")
    print(f"   🔢 Steps completados: {result.get('steps_completed', 0)}")
    print(f"   ⭐ Qualidade média: {format_quality_bar(result.get('avg_quality', 0))}")
    print(f"   🤖 Modelo utilizado: {result.get('model_provider', 'unknown')}")
    print()
    
    # Display quality per step
    quality_scores = result.get('quality_scores', [])
    if quality_scores:
        print("📈 QUALIDADE POR STEP:")
        for idx, score in enumerate(quality_scores, 1):
            bar = format_quality_bar(score)
            print(f"   Step {idx}: {bar}")
        print()
    
    # Display research plan
    plan = result.get('plan', [])
    if plan:
        print("📋 PLANO DE PESQUISA:")
        for idx, step in enumerate(plan, 1):
            print(f"   {idx}. {step}")
        print()
    
    # Display report
    report = result.get('report', '')
    print_separator('─')
    print("📄 RELATÓRIO COMPLETO:")
    print_separator('─')
    print()
    
    if report and len(report) > 100:
        print(report)
    else:
        print("⚠️  Relatório vazio ou muito curto.")
        print("   Mostrando resumo do plano de pesquisa:")
        print()
        for idx, step in enumerate(plan, 1):
            print(f"   {idx}. {step}")
    
    print()
    print_separator('─')
    
    # Validate and convert
    print()
    print("🔄 VALIDANDO E CONVERTENDO PARA FACTS...")
    print()
    
    is_valid = validate_research_result(result)
    print(f"   Validação: {'✅ VÁLIDO' if is_valid else '❌ INVÁLIDO'}")
    
    if is_valid:
        facts = convert_research_to_facts(
            research_result=result,
            org_id="org_demo",
            query=query,
            user_id="user_demo"
        )
        
        print(f"   Facts criados: {len(facts)}")
        print()
        
        print("📦 FACTS GERADOS:")
        for idx, fact in enumerate(facts, 1):
            print(f"\n   Fact {idx}:")
            print(f"   ├─ ID: {fact['fact_id']}")
            print(f"   ├─ Tipo: {fact['fact_type']}")
            print(f"   ├─ Confiança: {fact['confidence']:.3f}")
            print(f"   ├─ Fonte: {fact['source']}")
            print(f"   ├─ Status: {fact['status']}")
            print(f"   ├─ Prioridade: {'⭐ SIM' if fact.get('_deepresearch_priority') else 'Não'}")
            
            content_preview = fact['content'][:150]
            if len(fact['content']) > 150:
                content_preview += "..."
            print(f"   └─ Conteúdo: {content_preview}")
    
    print()
    print_separator('━')
    print("🎉 TESTE CONCLUÍDO COM SUCESSO!")
    print_separator('━')
    print()


if __name__ == "__main__":
    try:
        test_research_full()
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n\n❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()
