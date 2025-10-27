"""
FASE 3 - Teste de Conexão com Deep Research Agent no Azure
Valida conectividade e funcionalidade básica
"""

import sys
import os
from pathlib import Path

# Add agent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_azure_connection():
    """Test connection to Deep Research Agent on Azure"""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3.1.1 - TESTE DE CONEXÃO AZURE")
    logger.info("="*80)
    
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        
        # Get URL from environment
        base_url = os.environ.get(
            "DEEPRESEARCH_BASE_URL",
            "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
        )
        
        logger.info(f"🌐 Connecting to: {base_url}")
        
        # Initialize client
        client = DeepResearchClient(base_url=base_url)
        logger.info("✅ Client initialized")
        
        # Health check
        logger.info("🏥 Performing health check...")
        health_ok = client.health_check()
        
        if health_ok:
            logger.info("✅ Deep Research Agent on Azure is HEALTHY!")
            logger.info("🎉 Connection successful!")
            return True
        else:
            logger.error("❌ Health check failed")
            logger.error("The service may be down or the URL is incorrect")
            return False
            
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}", exc_info=True)
        return False


def test_simple_research():
    """Test a simple research query"""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3.1.2 - TESTE DE PESQUISA SIMPLES")
    logger.info("="*80)
    
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        
        base_url = os.environ.get(
            "DEEPRESEARCH_BASE_URL",
            "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
        )
        
        client = DeepResearchClient(base_url=base_url)
        
        # Simple test query
        query = "What are the main benefits of AI agents in 2025?"
        logger.info(f"🔍 Query: {query}")
        logger.info("⏳ Executing research (this may take 30-60 seconds)...")
        
        start_time = datetime.now()
        
        result = client.research_sync(
            topic=query,  # Use 'topic' parameter
            model_provider="openai",
            max_steps=3,  # Quick test with 3 steps
            correlation_id="test-simple-research"
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if not result:
            logger.error("❌ Research returned no result")
            return False
        
        logger.info(f"\n✅ Research completed in {duration:.1f}s")
        logger.info(f"📊 Steps completed: {result.get('steps_completed', 0)}")
        logger.info(f"⭐ Quality score: {result.get('avg_quality', 0):.1f}/10")
        logger.info(f"🔧 Model used: {result.get('model_provider', 'unknown')}")
        logger.info(f"📝 Report length: {len(result.get('report', ''))} characters")
        
        # Show first 200 chars of report
        report = result.get('report', '')
        if report:
            logger.info(f"\n📄 Report preview:\n{report[:200]}...\n")
        
        # Show plan
        plan = result.get('plan', [])
        if plan:
            logger.info("📋 Research plan:")
            for idx, step in enumerate(plan[:3], 1):
                logger.info(f"   {idx}. {step}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Simple research test failed: {e}", exc_info=True)
        return False


def test_conversion_with_real_data():
    """Test conversion with real research data"""
    logger.info("\n" + "="*80)
    logger.info("ETAPA 3.1.3 - TESTE DE CONVERSÃO COM DADOS REAIS")
    logger.info("="*80)
    
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        from agent.integrations.research_converter import (
            convert_research_to_facts,
            validate_research_result
        )
        
        base_url = os.environ.get(
            "DEEPRESEARCH_BASE_URL",
            "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
        )
        
        client = DeepResearchClient(base_url=base_url)
        
        # Execute research
        query = "AI agent integration best practices"
        logger.info(f"🔍 Researching: {query}")
        
        result = client.research_sync(
            topic=query,  # Use 'topic' parameter
            model_provider="openai",
            max_steps=3,
            correlation_id="test-conversion"
        )
        
        if not result:
            logger.error("❌ Research failed")
            return False
        
        # Validate
        logger.info("✅ Research completed, validating...")
        is_valid = validate_research_result(result)
        logger.info(f"Validation result: {'✅ VALID' if is_valid else '❌ INVALID'}")
        
        if not is_valid:
            logger.error("❌ Validation failed")
            return False
        
        # Convert
        logger.info("🔄 Converting to Meeting Agent facts...")
        facts = convert_research_to_facts(
            research_result=result,
            org_id="org_test",
            query=query,
            user_id="test_user"
        )
        
        logger.info(f"✅ Converted to {len(facts)} facts")
        
        # Show details
        for idx, fact in enumerate(facts, 1):
            logger.info(f"\nFact {idx}:")
            logger.info(f"  - ID: {fact['fact_id']}")
            logger.info(f"  - Type: {fact['fact_type']}")
            logger.info(f"  - Confidence: {fact['confidence']:.3f}")
            logger.info(f"  - Source: {fact['source']}")
            logger.info(f"  - Priority: {fact.get('_deepresearch_priority', False)}")
            logger.info(f"  - Content: {fact['content'][:100]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Conversion test failed: {e}", exc_info=True)
        return False


def main():
    """Run Phase 3.1 tests"""
    logger.info("\n" + "🧪 FASE 3.1 - TESTES DE CONFIGURAÇÃO E CONEXÃO" + "\n")
    
    results = {}
    
    # Test 1: Azure connection
    logger.info("▶️  Iniciando Teste 1: Conexão Azure\n")
    results["azure_connection"] = test_azure_connection()
    
    if not results["azure_connection"]:
        logger.error("\n❌ FALHA NA CONEXÃO - Abortando testes seguintes")
        logger.error("Verifique se o Deep Research Agent está rodando no Azure")
        logger.error(f"URL: {os.environ.get('DEEPRESEARCH_BASE_URL', 'not set')}")
        return 1
    
    # Test 2: Simple research
    logger.info("\n▶️  Iniciando Teste 2: Pesquisa Simples\n")
    results["simple_research"] = test_simple_research()
    
    if not results["simple_research"]:
        logger.warning("\n⚠️  Pesquisa simples falhou - continuando com último teste")
    
    # Test 3: Conversion with real data
    logger.info("\n▶️  Iniciando Teste 3: Conversão com Dados Reais\n")
    results["conversion_real_data"] = test_conversion_with_real_data()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("RESUMO FASE 3.1")
    logger.info("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    total_pass = sum(results.values())
    total_tests = len(results)
    
    logger.info(f"\nTotal: {total_pass}/{total_tests} tests passed")
    
    if total_pass == total_tests:
        logger.info("\n🎉 FASE 3.1 COMPLETADA COM SUCESSO!")
        logger.info("\n📋 PRÓXIMO PASSO: FASE 3.2 - Testes de Integração E2E")
        logger.info("Digite 'CONTINUAR' para prosseguir com Fase 3.2")
        return 0
    elif results["azure_connection"]:
        logger.info("\n⚠️  Alguns testes falharam, mas conexão Azure OK")
        logger.info("Pode ser necessário ajustar configurações")
        return 1
    else:
        logger.error("\n❌ FASE 3.1 FALHOU - Conexão Azure não estabelecida")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
