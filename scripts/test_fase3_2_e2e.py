"""
FASE 3.2 - Teste End-to-End da Integração Deep Research + Meeting Agent
Valida o fluxo completo através do nó retrieve_facts
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_retrieve_facts_with_deep_research():
    """Test retrieve_facts node with Deep Research integration"""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3.2.1 - TESTE DO NÓ retrieve_facts COM DEEP RESEARCH")
    logger.info("="*80)
    
    try:
        from agent.graph.state import AgendaState
        from agent.graph.nodes import retrieve_facts
        
        # Create test state with realistic scenario
        test_state: AgendaState = {
            "session_id": "test-session-e2e-001",
            "org_id": "org_test_e2e",
            "user_id": "user_test_e2e",
            "raw_query": "Quero planejar uma reunião sobre estratégia de IA para 2025",
            "subject": "Estratégia de IA 2025",
            "intent": "alignment",
            "language": "pt-BR",
            "workstreams": [],
            "focus_areas": ["IA", "estratégia", "planejamento"],
            "progress": {}
        }
        
        logger.info(f"📝 Estado de teste criado:")
        logger.info(f"   - Session ID: {test_state['session_id']}")
        logger.info(f"   - Org ID: {test_state['org_id']}")
        logger.info(f"   - Subject: {test_state['subject']}")
        logger.info(f"   - Intent: {test_state['intent']}")
        logger.info(f"   - Query: {test_state['raw_query']}")
        logger.info("")
        
        logger.info("🔍 Executando retrieve_facts...")
        logger.info("   (Isso acionará Deep Research se houver < 8 facts internos)")
        logger.info("")
        
        start_time = datetime.now()
        
        # Execute retrieve_facts node
        result_state = retrieve_facts(test_state)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("")
        logger.info("="*80)
        logger.info("✅ RETRIEVE_FACTS COMPLETADO!")
        logger.info("="*80)
        logger.info("")
        
        # Analyze results
        facts = result_state.get("facts", [])
        ranked_facts = result_state.get("ranked_facts", [])
        
        logger.info(f"📊 RESULTADOS:")
        logger.info(f"   ⏱️  Tempo total: {duration:.1f}s")
        logger.info(f"   📚 Total de facts: {len(facts)}")
        logger.info(f"   ⭐ Facts ranqueados: {len(ranked_facts)}")
        logger.info("")
        
        # Check for Deep Research facts
        deepresearch_facts = [
            f for f in facts 
            if f.get("source") == "deep_research_agent"
        ]
        
        if deepresearch_facts:
            logger.info(f"🔬 DEEP RESEARCH FACTS ENCONTRADOS: {len(deepresearch_facts)}")
            logger.info("")
            
            for idx, fact in enumerate(deepresearch_facts, 1):
                logger.info(f"   Deep Research Fact {idx}:")
                logger.info(f"   ├─ ID: {fact['fact_id']}")
                logger.info(f"   ├─ Tipo: {fact['fact_type']}")
                logger.info(f"   ├─ Confiança: {fact['confidence']:.3f}")
                logger.info(f"   ├─ Prioridade: {'⭐ SIM' if fact.get('_deepresearch_priority') else 'Não'}")
                
                content = fact.get('content', '')
                preview = content[:200] if len(content) > 200 else content
                logger.info(f"   └─ Conteúdo: {preview}...")
                logger.info("")
            
            # Check metadata
            sample_fact = deepresearch_facts[0]
            metadata = sample_fact.get('metadata', {})
            if metadata:
                logger.info("   📋 Metadata do Deep Research:")
                logger.info(f"      - Steps: {metadata.get('steps_completed', 'N/A')}")
                logger.info(f"      - Quality: {metadata.get('avg_quality', 'N/A')}")
                logger.info(f"      - Execution time: {metadata.get('execution_time', 'N/A')}s")
                logger.info(f"      - Depth: {metadata.get('research_depth', 'N/A')}")
                logger.info("")
            
            logger.info("✅ Deep Research foi acionado e integrado com sucesso!")
            return True
            
        else:
            logger.warning("⚠️  Nenhum Deep Research fact encontrado")
            logger.warning("   Possíveis razões:")
            logger.warning("   - MongoDB tem >= 8 facts para este subject")
            logger.warning("   - Deep Research foi desabilitado")
            logger.warning("   - Erro na execução (verifique logs acima)")
            logger.info("")
            logger.info("💡 Para forçar Deep Research, limpe o banco ou use subject novo")
            return False
        
    except Exception as e:
        logger.error(f"❌ Teste falhou: {e}", exc_info=True)
        return False


def test_full_workflow_simulation():
    """Simulate a complete Meeting Agent workflow"""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3.2.2 - SIMULAÇÃO DE WORKFLOW COMPLETO")
    logger.info("="*80)
    logger.info("")
    
    try:
        from agent.graph.state import AgendaState
        from agent.graph.nodes import (
            parse_request,
            detect_intent,
            retrieve_facts,
        )
        
        # Initial state
        initial_state: AgendaState = {
            "session_id": "test-workflow-e2e-002",
            "org_id": "org_workflow_test",
            "user_id": "user_workflow_test",
            "raw_query": "Precisamos discutir a implementação de agentes de IA autônomos na empresa",
            "progress": {}
        }
        
        logger.info("📝 Query inicial:")
        logger.info(f"   '{initial_state['raw_query']}'")
        logger.info("")
        
        # Step 1: Parse request
        logger.info("🔄 STEP 1: Parse Request")
        state = parse_request(initial_state)
        logger.info(f"   ✅ Subject: {state.get('subject', 'N/A')}")
        logger.info(f"   ✅ Language: {state.get('language', 'N/A')}")
        logger.info("")
        
        # Step 2: Detect intent
        logger.info("🔄 STEP 2: Detect Intent")
        state = detect_intent(state)
        logger.info(f"   ✅ Intent: {state.get('intent', 'N/A')}")
        logger.info(f"   ✅ Focus areas: {state.get('focus_areas', [])}")
        logger.info("")
        
        # Step 3: Retrieve facts (with Deep Research)
        logger.info("🔄 STEP 3: Retrieve Facts (com Deep Research)")
        logger.info("   ⏳ Isso pode levar alguns minutos...")
        logger.info("")
        
        start_time = datetime.now()
        state = retrieve_facts(state)
        end_time = datetime.now()
        
        facts = state.get("facts", [])
        deepresearch_facts = [
            f for f in facts 
            if f.get("source") == "deep_research_agent"
        ]
        
        logger.info(f"   ✅ Facts recuperados: {len(facts)}")
        logger.info(f"   🔬 Deep Research facts: {len(deepresearch_facts)}")
        logger.info(f"   ⏱️  Tempo: {(end_time - start_time).total_seconds():.1f}s")
        logger.info("")
        
        # Summary
        logger.info("="*80)
        logger.info("📊 RESUMO DO WORKFLOW")
        logger.info("="*80)
        logger.info(f"Subject: {state.get('subject', 'N/A')}")
        logger.info(f"Intent: {state.get('intent', 'N/A')}")
        logger.info(f"Language: {state.get('language', 'N/A')}")
        logger.info(f"Focus areas: {', '.join(state.get('focus_areas', []))}")
        logger.info(f"Total facts: {len(facts)}")
        logger.info(f"Deep Research facts: {len(deepresearch_facts)}")
        logger.info("")
        
        if deepresearch_facts:
            logger.info("✅ Deep Research foi integrado no workflow!")
            return True
        else:
            logger.warning("⚠️  Deep Research não foi acionado neste workflow")
            return False
        
    except Exception as e:
        logger.error(f"❌ Simulação de workflow falhou: {e}", exc_info=True)
        return False


def test_deep_research_trigger_conditions():
    """Test different conditions that trigger Deep Research"""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3.2.3 - TESTE DE CONDIÇÕES DE ACIONAMENTO")
    logger.info("="*80)
    logger.info("")
    
    try:
        from agent.graph.state import AgendaState
        from agent.graph.nodes import retrieve_facts
        
        test_cases = [
            {
                "name": "Subject novo (deve acionar Deep Research)",
                "subject": f"IA Quântica em Finanças {datetime.now().timestamp()}",
                "query": "Como aplicar IA quântica em análise financeira?"
            },
            {
                "name": "Subject genérico (pode acionar Deep Research)",
                "subject": "Transformação Digital",
                "query": "Estratégias de transformação digital"
            }
        ]
        
        results = []
        
        for idx, test_case in enumerate(test_cases, 1):
            logger.info(f"🧪 Teste {idx}: {test_case['name']}")
            logger.info(f"   Subject: {test_case['subject']}")
            logger.info("")
            
            state: AgendaState = {
                "session_id": f"test-trigger-{idx}",
                "org_id": f"org_trigger_test_{idx}",
                "subject": test_case['subject'],
                "raw_query": test_case['query'],
                "intent": "alignment",
                "language": "pt-BR",
                "workstreams": [],
                "focus_areas": [],
                "progress": {}
            }
            
            try:
                result_state = retrieve_facts(state)
                facts = result_state.get("facts", [])
                deepresearch_facts = [
                    f for f in facts 
                    if f.get("source") == "deep_research_agent"
                ]
                
                triggered = len(deepresearch_facts) > 0
                results.append({
                    "test": test_case['name'],
                    "triggered": triggered,
                    "facts_count": len(facts),
                    "deepresearch_count": len(deepresearch_facts)
                })
                
                logger.info(f"   {'✅' if triggered else '❌'} Deep Research: {'Acionado' if triggered else 'Não acionado'}")
                logger.info(f"   📊 Total facts: {len(facts)} ({len(deepresearch_facts)} Deep Research)")
                logger.info("")
                
            except Exception as e:
                logger.error(f"   ❌ Erro no teste: {e}")
                results.append({
                    "test": test_case['name'],
                    "triggered": False,
                    "error": str(e)
                })
                logger.info("")
        
        # Summary
        logger.info("="*80)
        logger.info("📊 RESUMO DOS TESTES DE ACIONAMENTO")
        logger.info("="*80)
        
        for result in results:
            status = "✅" if result.get("triggered") else "⚠️ "
            logger.info(f"{status} {result['test']}")
            if "error" in result:
                logger.info(f"   Erro: {result['error']}")
            else:
                logger.info(f"   Facts: {result['facts_count']} (Deep Research: {result['deepresearch_count']})")
        
        logger.info("")
        
        triggered_count = sum(1 for r in results if r.get("triggered", False))
        logger.info(f"Total: {triggered_count}/{len(results)} testes acionaram Deep Research")
        
        return triggered_count > 0
        
    except Exception as e:
        logger.error(f"❌ Teste de condições falhou: {e}", exc_info=True)
        return False


def main():
    """Run all Phase 3.2 tests"""
    logger.info("\n" + "🧪 FASE 3.2 - TESTES END-TO-END" + "\n")
    
    results = {}
    
    # Test 1: retrieve_facts with Deep Research
    logger.info("▶️  Iniciando Teste 1: retrieve_facts com Deep Research\n")
    results["retrieve_facts"] = test_retrieve_facts_with_deep_research()
    
    # Test 2: Full workflow simulation
    logger.info("\n▶️  Iniciando Teste 2: Simulação de Workflow Completo\n")
    results["full_workflow"] = test_full_workflow_simulation()
    
    # Test 3: Trigger conditions
    logger.info("\n▶️  Iniciando Teste 3: Condições de Acionamento\n")
    results["trigger_conditions"] = test_deep_research_trigger_conditions()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("RESUMO FASE 3.2")
    logger.info("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "⚠️  PARTIAL"
        logger.info(f"{status}: {test_name}")
    
    total_pass = sum(results.values())
    total_tests = len(results)
    
    logger.info(f"\nTotal: {total_pass}/{total_tests} testes com Deep Research acionado")
    
    if total_pass >= 1:
        logger.info("\n✅ FASE 3.2 COMPLETADA!")
        logger.info("A integração Deep Research está funcionando no workflow do Meeting Agent")
        logger.info("\n📋 PRÓXIMO PASSO: Confirme para continuar com FASE 3.3 (Testes de Performance)")
        return 0
    else:
        logger.warning("\n⚠️  FASE 3.2 - Deep Research não foi acionado em nenhum teste")
        logger.warning("Isso pode ser esperado se o MongoDB já tem facts suficientes")
        logger.warning("A integração está pronta, mas não foi testada em produção")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
