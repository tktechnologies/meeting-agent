"""
Teste rápido da configuração inteligente de Deep Research

Valida:
1. Detecção de complexidade
2. Configuração dinâmica de steps
3. Fallback automático em caso de timeout
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.integrations.research_config import get_research_config, ResearchConfig, TopicComplexity


def test_complexity_detection():
    """Testa detecção de complexidade."""
    print("\n" + "="*80)
    print("🧪 TESTE 1: DETECÇÃO DE COMPLEXIDADE")
    print("="*80 + "\n")
    
    config = ResearchConfig()
    
    test_cases = [
        ("Status do projeto X", TopicComplexity.SIMPLE),
        ("Análise do novo processo de onboarding", TopicComplexity.MODERATE),
        ("Estratégia de transformação digital para 2025", TopicComplexity.COMPLEX),
        ("Decisão crítica sobre arquitetura de IA", TopicComplexity.COMPLEX),
    ]
    
    for topic, expected in test_cases:
        detected = config.detect_complexity(topic)
        status = "✅" if detected == expected else "❌"
        print(f"{status} '{topic}'")
        print(f"   Esperado: {expected.value} | Detectado: {detected.value}\n")


def test_optimal_config():
    """Testa configuração ótima."""
    print("\n" + "="*80)
    print("🧪 TESTE 2: CONFIGURAÇÃO ÓTIMA")
    print("="*80 + "\n")
    
    test_cases = [
        {
            "topic": "Status do projeto",
            "intent": "status",
            "expected_max": 3
        },
        {
            "topic": "Transformação digital e inovação",
            "intent": "decision",
            "expected_max": 5  # Limited by DEEPRESEARCH_MAX_STEPS=5
        },
        {
            "topic": "Reunião de alinhamento trimestral",
            "intent": "alignment",
            "expected_max": 5
        }
    ]
    
    config = ResearchConfig(max_steps=5, fallback_steps=3)
    
    for test in test_cases:
        optimal = config.get_optimal_config(
            topic=test["topic"],
            intent=test["intent"]
        )
        
        print(f"📝 Tópico: {test['topic']}")
        print(f"   Intent: {test['intent']}")
        print(f"   Complexidade: {optimal['complexity']}")
        print(f"   Steps: {optimal['max_steps']} (fallback: {optimal['fallback_steps']})")
        print(f"   Timeout: {optimal['timeout']}s")
        print(f"   Reasoning: {optimal['reasoning']}")
        
        if optimal['max_steps'] <= test['expected_max']:
            print(f"   ✅ Steps dentro do esperado (<= {test['expected_max']})")
        else:
            print(f"   ❌ Steps acima do esperado ({optimal['max_steps']} > {test['expected_max']})")
        
        print()


def test_should_use_deep_research():
    """Testa decisão de usar Deep Research."""
    print("\n" + "="*80)
    print("🧪 TESTE 3: DECISÃO DE USO")
    print("="*80 + "\n")
    
    test_cases = [
        {
            "topic": "Status do projeto",
            "facts_count": 2,
            "should_use": True,
            "reason": "poucos facts"
        },
        {
            "topic": "Status do projeto",
            "facts_count": 10,
            "should_use": False,
            "reason": "facts suficientes"
        },
        {
            "topic": "Estratégia de IA para 2025",
            "facts_count": 5,
            "should_use": True,
            "reason": "tópico complexo"
        },
        {
            "topic": "Estratégia de IA para 2025",
            "facts_count": 12,
            "should_use": True,
            "reason": "tópico complexo mesmo com facts"
        }
    ]
    
    for test in test_cases:
        decision = get_research_config(
            topic=test["topic"],
            intent="alignment",
            internal_facts_count=test["facts_count"]
        )
        
        print(f"📝 Tópico: {test['topic']}")
        print(f"   Facts: {test['facts_count']}")
        print(f"   Decisão: {'✅ Usar' if decision['should_use'] else '❌ Não usar'}")
        print(f"   Motivo: {decision['reason']}")
        
        if decision['should_use'] == test['should_use']:
            print(f"   ✅ Decisão correta")
        else:
            print(f"   ❌ Decisão incorreta (esperado: {test['should_use']})")
        
        print()


def test_time_budget():
    """Testa restrição de tempo."""
    print("\n" + "="*80)
    print("🧪 TESTE 4: TIME BUDGET")
    print("="*80 + "\n")
    
    config = ResearchConfig(max_steps=10)  # Sem limite de steps
    
    test_cases = [
        ("Estratégia complexa", 120, 3),   # 120s = ~3 steps
        ("Estratégia complexa", 240, 6),   # 240s = ~6 steps
        ("Estratégia complexa", 400, 10),  # 400s = ~10 steps
    ]
    
    for topic, budget, expected_max_steps in test_cases:
        optimal = config.get_optimal_config(
            topic=topic,
            intent="decision",
            time_budget=budget
        )
        
        print(f"📝 Budget: {budget}s")
        print(f"   Steps: {optimal['max_steps']} (esperado: <= {expected_max_steps})")
        print(f"   Timeout: {optimal['timeout']}s")
        
        if optimal['max_steps'] <= expected_max_steps:
            print(f"   ✅ Steps ajustados corretamente")
        else:
            print(f"   ❌ Steps não ajustados ({optimal['max_steps']} > {expected_max_steps})")
        
        print()


def main():
    """Executa todos os testes."""
    print("\n" + "="*80)
    print("🚀 TESTE DE CONFIGURAÇÃO INTELIGENTE - DEEP RESEARCH")
    print("="*80)
    
    try:
        test_complexity_detection()
        test_optimal_config()
        test_should_use_deep_research()
        test_time_budget()
        
        print("\n" + "="*80)
        print("✅ TODOS OS TESTES COMPLETADOS")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
