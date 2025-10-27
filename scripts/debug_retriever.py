"""
Debug do MultiStrategyRetriever
Identifica por que está falhando no retrieve_facts
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
import traceback

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_retriever_direct():
    """Test MultiStrategyRetriever directly"""
    
    print("\n" + "="*80)
    print("🔍 DEBUG DO MULTISTRATEGYRETRIEVER")
    print("="*80)
    print()
    
    # Test 1: Import check
    print("1️⃣  Verificando imports...")
    try:
        from agent.retrievers.multi_strategy import MultiStrategyRetriever
        print("   ✅ MultiStrategyRetriever importado")
    except ImportError as e:
        print(f"   ❌ Erro ao importar: {e}")
        traceback.print_exc()
        return False
    
    # Test 2: Instantiation
    print("\n2️⃣  Criando instância do retriever...")
    try:
        org_id = "org_test_debug"
        retriever = MultiStrategyRetriever(org_id)
        print(f"   ✅ Retriever criado para org_id={org_id}")
    except Exception as e:
        print(f"   ❌ Erro ao criar retriever: {e}")
        traceback.print_exc()
        return False
    
    # Test 3: Simple retrieval
    print("\n3️⃣  Testando retrieve_all com subject...")
    try:
        subject = "Test Subject for Debug"
        workstream_ids = None
        
        print(f"   Subject: {subject}")
        print(f"   Workstream IDs: {workstream_ids}")
        print()
        
        result = retriever.retrieve_all(
            workstream_ids=workstream_ids,
            subject=subject
        )
        
        print(f"   ✅ retrieve_all executado com sucesso!")
        print(f"   📊 Facts retornados: {len(result.get('facts', []))}")
        print(f"   📈 Stats: {result.get('stats', {})}")
        
        facts = result.get('facts', [])
        if facts:
            print(f"\n   📝 Sample facts:")
            for idx, fact in enumerate(facts[:3], 1):
                print(f"      {idx}. {fact.get('fact_id', 'N/A')}: {fact.get('content', '')[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro durante retrieve_all: {e}")
        print(f"\n   🔍 Stack trace completo:")
        traceback.print_exc()
        
        # Additional debugging
        print(f"\n   🔬 Informações adicionais:")
        print(f"      - Tipo do erro: {type(e).__name__}")
        print(f"      - Mensagem: {str(e)}")
        
        return False


def test_database_connection():
    """Test database connection"""
    
    print("\n" + "="*80)
    print("🗄️  TESTE DE CONEXÃO COM BANCO DE DADOS")
    print("="*80)
    print()
    
    try:
        from agent import db_router as db
        
        print("1️⃣  Verificando configuração do banco...")
        print(f"   Database router importado: {db}")
        print()
        
        # Check which database is being used
        print("2️⃣  Identificando tipo de banco...")
        
        # Try to list facts
        try:
            org_id = "org_test_debug"
            print(f"   Tentando listar facts para org_id={org_id}")
            
            # Try to query facts
            facts = db.list_facts(org_id=org_id, limit=5)
            print(f"   ✅ Consulta executada com sucesso!")
            print(f"   📊 Facts encontrados: {len(facts)}")
            
            if facts:
                print(f"\n   📝 Sample facts:")
                for idx, fact in enumerate(facts[:3], 1):
                    print(f"      {idx}. {fact.get('fact_id', 'N/A')}")
            
            return True
            
        except Exception as e:
            print(f"   ⚠️  Erro ao listar facts: {e}")
            print(f"\n   Stack trace:")
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"   ❌ Erro ao conectar com banco: {e}")
        traceback.print_exc()
        return False


def test_retriever_methods():
    """Test individual retriever methods"""
    
    print("\n" + "="*80)
    print("🧪 TESTE DE MÉTODOS INDIVIDUAIS DO RETRIEVER")
    print("="*80)
    print()
    
    try:
        from agent.retrievers.multi_strategy import MultiStrategyRetriever
        
        org_id = "org_test_debug"
        retriever = MultiStrategyRetriever(org_id)
        
        # Test 1: Workstream retrieval
        print("1️⃣  Testando retrieve_by_workstream...")
        try:
            workstream_ids = ["ws_test_1", "ws_test_2"]
            facts = retriever.retrieve_by_workstream(workstream_ids)
            print(f"   ✅ Executado: {len(facts)} facts")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        # Test 2: Subject retrieval
        print("\n2️⃣  Testando retrieve_by_subject...")
        try:
            subject = "Test Subject"
            facts = retriever.retrieve_by_subject(subject, limit=10)
            print(f"   ✅ Executado: {len(facts)} facts")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            traceback.print_exc()
        
        # Test 3: Urgent retrieval
        print("\n3️⃣  Testando retrieve_urgent...")
        try:
            facts = retriever.retrieve_urgent(limit=5)
            print(f"   ✅ Executado: {len(facts)} facts")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro geral: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all debug tests"""
    
    print("\n🔬 DEBUG DO RETRIEVER - ANÁLISE COMPLETA\n")
    
    results = {}
    
    # Test 1: Database connection
    results['database'] = test_database_connection()
    
    # Test 2: Individual methods
    results['methods'] = test_retriever_methods()
    
    # Test 3: Direct retriever
    results['retriever'] = test_retriever_direct()
    
    # Summary
    print("\n" + "="*80)
    print("📊 RESUMO DO DEBUG")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ OK" if passed else "❌ FALHOU"
        print(f"{status}: {test_name}")
    
    total_pass = sum(results.values())
    total_tests = len(results)
    
    print(f"\nTotal: {total_pass}/{total_tests} testes passaram")
    
    if total_pass < total_tests:
        print("\n⚠️  PROBLEMAS IDENTIFICADOS!")
        print("Verifique os erros acima para detalhes.")
        
        if not results.get('database'):
            print("\n💡 Sugestão: Problema pode estar na conexão com o banco de dados")
            print("   - Verifique se MongoDB está rodando (se usando MongoDB)")
            print("   - Verifique permissões do SQLite (se usando SQLite)")
        
        if not results.get('methods'):
            print("\n💡 Sugestão: Problema pode estar nos métodos de busca")
            print("   - Verifique schemas/índices do banco")
            print("   - Verifique logs de erro acima")
        
        return 1
    else:
        print("\n✅ TODOS OS TESTES PASSARAM!")
        print("O retriever está funcionando corretamente.")
        print("O problema pode estar em outro lugar do retrieve_facts.")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
