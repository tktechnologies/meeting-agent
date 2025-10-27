"""
Teste direto do Deep Research no retrieve_facts
Força o acionamento do Deep Research mesmo sem MongoDB
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def test_deep_research_direct():
    """Test Deep Research integration directly"""
    
    print("\n" + "="*80)
    print("🔬 TESTE DIRETO DE DEEP RESEARCH")
    print("="*80)
    print()
    
    # Test 1: Import check
    print("1️⃣  Verificando imports...")
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        from agent.integrations.research_converter import convert_research_to_facts, validate_research_result
        print("   ✅ DeepResearchClient importado")
        print("   ✅ research_converter importado")
    except ImportError as e:
        print(f"   ❌ Erro de import: {e}")
        return False
    
    # Test 2: Check environment variable
    print("\n2️⃣  Verificando variável HAVE_DEEP_RESEARCH...")
    try:
        from agent.graph import nodes
        have_deep_research = getattr(nodes, 'HAVE_DEEP_RESEARCH', False)
        print(f"   HAVE_DEEP_RESEARCH = {have_deep_research}")
        
        if not have_deep_research:
            print("   ❌ HAVE_DEEP_RESEARCH is False!")
            print("   Verificando imports em nodes.py...")
            return False
        else:
            print("   ✅ HAVE_DEEP_RESEARCH is True")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Test 3: Direct API call
    print("\n3️⃣  Testando chamada direta da API...")
    try:
        base_url = os.environ.get(
            "DEEPRESEARCH_BASE_URL",
            "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
        )
        
        client = DeepResearchClient(base_url=base_url)
        print(f"   ✅ Cliente criado: {base_url}")
        
        # Health check
        print("   🏥 Health check...")
        is_healthy = client.health_check()
        print(f"   {'✅' if is_healthy else '❌'} Health: {is_healthy}")
        
        if not is_healthy:
            print("   ⚠️  API não está saudável, mas continuando...")
        
        # Quick research
        print("\n   🔍 Executando pesquisa rápida...")
        result = client.research_sync(
            topic="Test query para verificar integração",
            model_provider="openai",
            max_steps=3,
            correlation_id="direct-test"
        )
        
        print(f"   ✅ Pesquisa completada:")
        print(f"      - Steps: {result.get('steps_completed')}")
        print(f"      - Quality: {result.get('avg_quality'):.1f}/10")
        
        # Validate
        is_valid = validate_research_result(result)
        print(f"   {'✅' if is_valid else '❌'} Validação: {is_valid}")
        
        # Convert
        if is_valid:
            facts = convert_research_to_facts(
                research_result=result,
                org_id="test_org",
                query="test query",
                user_id="test_user"
            )
            print(f"   ✅ Convertido para {len(facts)} facts")
            
            if facts:
                fact = facts[0]
                print(f"\n   📦 Sample fact:")
                print(f"      - ID: {fact['fact_id']}")
                print(f"      - Type: {fact['fact_type']}")
                print(f"      - Confidence: {fact['confidence']:.3f}")
                print(f"      - Source: {fact['source']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro na chamada direta: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Check retrieve_facts code
    print("\n4️⃣  Verificando código do retrieve_facts...")
    try:
        import inspect
        from agent.graph.nodes import retrieve_facts
        
        source = inspect.getsource(retrieve_facts)
        
        if "HAVE_DEEP_RESEARCH" in source:
            print("   ✅ Código verifica HAVE_DEEP_RESEARCH")
        else:
            print("   ❌ Código NÃO verifica HAVE_DEEP_RESEARCH")
            
        if "DeepResearchClient" in source:
            print("   ✅ Código usa DeepResearchClient")
        else:
            print("   ❌ Código NÃO usa DeepResearchClient")
            
        if "deepresearch_client.research_sync" in source:
            print("   ✅ Código chama research_sync")
        else:
            print("   ❌ Código NÃO chama research_sync")
        
        # Check for the trigger condition
        if "len(all_facts) < 8" in source:
            print("   ✅ Condição de trigger encontrada (< 8 facts)")
        else:
            print("   ⚠️  Condição de trigger não encontrada")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao verificar código: {e}")
        return False


if __name__ == "__main__":
    success = test_deep_research_direct()
    
    print("\n" + "="*80)
    if success:
        print("✅ TESTE DIRETO PASSOU!")
        print("="*80)
        print()
        print("A integração Deep Research está funcionando.")
        print("Se retrieve_facts não está acionando, pode ser:")
        print("  1. Há >= 8 facts no MongoDB para o subject")
        print("  2. Erro no retriever antes de chegar no Deep Research")
        print("  3. HAVE_DEEP_RESEARCH é False no contexto")
        sys.exit(0)
    else:
        print("❌ TESTE DIRETO FALHOU!")
        print("="*80)
        sys.exit(1)
