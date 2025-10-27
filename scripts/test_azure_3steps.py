"""
Teste de research com 3 steps (mínimo válido)

Valida que o Deep Research Agent no Azure aceita e processa
requisições com 3 steps corretamente.
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


def test_research_3_steps():
    """Teste com 3 steps (mínimo aceito pelo Agent)."""
    
    print("\n" + "="*80)
    print("🧪 TESTE: RESEARCH COM 3 STEPS (MÍNIMO VÁLIDO)")
    print("="*80 + "\n")
    
    try:
        client = httpx.Client(timeout=600.0, http2=True)
        
        payload = {
            "topic": "Python best practices 2025",
            "model_provider": "openai",
            "max_steps": 3,  # Mínimo aceito
            "search_provider": "tavily",
            "correlation_id": "test-3steps-valid"
        }
        
        print(f"📤 Request:")
        print(json.dumps(payload, indent=2))
        
        print(f"\n📡 POST {AZURE_URL}/research")
        print(f"⏱️  Aguardando... (timeout 600s)")
        
        start = time.time()
        response = client.post(f"{AZURE_URL}/research", json=payload)
        elapsed = time.time() - start
        
        print(f"\n✅ Resposta recebida em {elapsed:.1f}s")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n📊 RESULTADO:")
            print(f"   Steps completados: {data.get('steps_completed', 0)}")
            print(f"   Qualidade média: {data.get('avg_quality', 0):.1f}/10")
            print(f"   Tempo total: {data.get('total_time_seconds', 0):.1f}s")
            print(f"   Report length: {len(data.get('report', ''))} chars")
            print(f"   Search steps: {len(data.get('search_steps', []))}")
            
            if data.get('avg_quality', 0) > 0:
                print(f"\n✅ SUCESSO! Research funcionou corretamente")
                
                # Show first paragraph of report
                report = data.get('report', '')
                if report:
                    first_para = report.split('\n\n')[0]
                    print(f"\n📄 Primeiro parágrafo do report:")
                    print(f"   {first_para[:200]}...")
                
                return True
            else:
                print(f"\n⚠️  Quality = 0, algo ainda está errado")
                
                # Debug search steps
                if data.get('search_steps'):
                    print(f"\n🔍 Analisando search steps:")
                    for i, step in enumerate(data['search_steps']):
                        print(f"\n   Step {i+1}:")
                        print(f"      Query: {step.get('query', 'N/A')}")
                        print(f"      Results: {step.get('results_count', 0)}")
                        print(f"      Status: {step.get('status', 'unknown')}")
                        if step.get('error'):
                            print(f"      ❌ Error: {step['error']}")
                
                return False
        else:
            print(f"\n❌ Erro {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except httpx.TimeoutException:
        print(f"\n❌ TIMEOUT após {time.time() - start:.1f}s")
        return False
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executa teste."""
    print("\n" + "="*80)
    print("🚀 VALIDAÇÃO: DEEP RESEARCH COM 3 STEPS")
    print("="*80)
    print(f"\nURL: {AZURE_URL}")
    print(f"Data/Hora: {datetime.now().isoformat()}")
    
    success = test_research_3_steps()
    
    print("\n" + "="*80)
    if success:
        print("✅ TESTE PASSOU - Deep Research funcionando corretamente!")
        print("="*80 + "\n")
        return 0
    else:
        print("❌ TESTE FALHOU - Verificar logs do Azure")
        print("="*80 + "\n")
        print("Comandos úteis:")
        print("  az containerapp logs show -n deepresearch-agent -g TK_Technologies --tail 50")
        return 1


if __name__ == "__main__":
    sys.exit(main())
