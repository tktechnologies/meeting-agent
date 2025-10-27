"""
Test Deep Research Integration with Meeting Agent
Validates the complete flow: retrieve_facts -> Deep Research -> conversion -> ranking
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


def test_converter():
    """Test research_converter with sample data"""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Research Converter")
    logger.info("="*80)
    
    from agent.integrations.research_converter import (
        convert_research_to_facts,
        validate_research_result
    )
    
    # Sample Deep Research result
    sample_research = {
        "report": """## Executive Summary

This is a comprehensive analysis of AI agent architectures.

## Key Findings

- AI agents use LangGraph for workflow orchestration
- Multi-model support is essential for production systems
- Tavily provides reliable search results

## Analysis

Deep dive into implementation patterns shows that successful agents combine:
1. Robust error handling
2. Health monitoring
3. Graceful degradation

## Recommendations

Consider implementing circuit breakers and retry logic for external API calls.
""",
        "plan": [
            "Research AI agent architectures",
            "Analyze LangGraph workflows",
            "Review multi-model implementations",
            "Study search integration patterns"
        ],
        "steps_completed": 8,
        "quality_scores": [7.5, 8.0, 8.2, 7.8, 8.5, 8.1, 7.9, 8.3],
        "avg_quality": 8.0,
        "execution_time": 45.3,
        "model_provider": "openai",
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": "test-123"
    }
    
    # Validate
    is_valid = validate_research_result(sample_research)
    logger.info(f"✅ Validation result: {is_valid}")
    
    if not is_valid:
        logger.error("❌ Sample research failed validation!")
        return False
    
    # Convert
    facts = convert_research_to_facts(
        research_result=sample_research,
        org_id="org_test",
        query="AI agent architectures",
        user_id="user_test"
    )
    
    logger.info(f"✅ Converted to {len(facts)} facts")
    
    for idx, fact in enumerate(facts, 1):
        logger.info(f"\nFact {idx}:")
        logger.info(f"  - ID: {fact['fact_id']}")
        logger.info(f"  - Type: {fact['fact_type']}")
        logger.info(f"  - Confidence: {fact['confidence']:.2f}")
        logger.info(f"  - Content: {fact['content'][:100]}...")
        logger.info(f"  - Payload keys: {list(fact.get('payload', {}).keys())}")
    
    return len(facts) > 0


def test_deepresearch_client():
    """Test DeepResearchClient health check"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Deep Research Client")
    logger.info("="*80)
    
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        
        client = DeepResearchClient()
        logger.info(f"✅ Client initialized with URL: {client.base_url}")
        
        # Health check
        logger.info("Checking Deep Research API health...")
        health_ok = client.health_check()
        
        if health_ok:
            logger.info("✅ Deep Research API is healthy!")
            return True
        else:
            logger.warning("⚠️  Deep Research API health check failed")
            logger.info("This is expected if the service is not running")
            return False
            
    except Exception as e:
        logger.error(f"❌ Client test failed: {e}")
        return False


def test_integration_imports():
    """Test that all imports work"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Integration Imports")
    logger.info("="*80)
    
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        logger.info("✅ DeepResearchClient imported")
        
        from agent.integrations.research_converter import (
            convert_research_to_facts,
            validate_research_result
        )
        logger.info("✅ research_converter functions imported")
        
        from agent.graph.nodes import retrieve_facts
        logger.info("✅ retrieve_facts node imported")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False


def test_retrieve_facts_mock():
    """Test retrieve_facts node with mock state"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: retrieve_facts Node (Mock)")
    logger.info("="*80)
    
    try:
        from agent.graph.state import AgendaState
        from agent.graph.nodes import retrieve_facts
        
        # Create mock state
        mock_state: AgendaState = {
            "org_id": "org_test",
            "subject": "Test AI agent integration",
            "raw_query": "How to integrate AI agents?",
            "intent": "alignment",
            "language": "pt-BR",
            "workstreams": [],
            "focus_areas": ["AI", "integration", "architecture"],
            "user_id": "user_test",
            "progress": {}
        }
        
        logger.info("Calling retrieve_facts with mock state...")
        logger.info("(This will attempt Deep Research if <8 facts found)")
        
        # Note: This will actually call the API if available
        result_state = retrieve_facts(mock_state)
        
        facts = result_state.get("facts", [])
        logger.info(f"✅ Retrieved {len(facts)} facts total")
        
        # Check for Deep Research facts
        deepresearch_facts = [f for f in facts if f.get("source") == "deep_research_agent"]
        if deepresearch_facts:
            logger.info(f"✅ Found {len(deepresearch_facts)} Deep Research facts!")
            logger.info(f"   First Deep Research fact: {deepresearch_facts[0]['fact_id']}")
        else:
            logger.info("ℹ️  No Deep Research facts (may be disabled or unavailable)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ retrieve_facts test failed: {e}", exc_info=True)
        return False


def test_full_integration():
    """Test complete integration with real Deep Research API"""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Full Integration (Real API)")
    logger.info("="*80)
    
    try:
        from agent.integrations.deepresearch_client import DeepResearchClient
        from agent.integrations.research_converter import convert_research_to_facts, validate_research_result
        
        client = DeepResearchClient()
        
        # Check health first
        if not client.health_check():
            logger.warning("⚠️  API not healthy - skipping full integration test")
            return False
        
        # Execute real research
        logger.info("Executing Deep Research with real API...")
        query = "What are the latest developments in AI agent architectures in 2025?"
        
        research_result = client.research_sync(
            query=query,
            max_steps=5,  # Shorter for testing
            search_provider="tavily"
        )
        
        if not research_result:
            logger.error("❌ Research returned no result")
            return False
        
        logger.info(f"✅ Research completed:")
        logger.info(f"   - Steps: {research_result.get('steps_completed')}")
        logger.info(f"   - Quality: {research_result.get('avg_quality'):.1f}/10")
        logger.info(f"   - Time: {research_result.get('execution_time'):.1f}s")
        logger.info(f"   - Report length: {len(research_result.get('report', ''))} chars")
        
        # Validate
        is_valid = validate_research_result(research_result)
        logger.info(f"✅ Validation: {is_valid}")
        
        if not is_valid:
            logger.error("❌ Research result validation failed")
            return False
        
        # Convert
        facts = convert_research_to_facts(
            research_result=research_result,
            org_id="org_test",
            query=query,
            user_id="user_test"
        )
        
        logger.info(f"✅ Converted to {len(facts)} facts")
        
        for idx, fact in enumerate(facts[:3], 1):  # Show first 3
            logger.info(f"\nFact {idx}:")
            logger.info(f"  - Type: {fact['fact_type']}")
            logger.info(f"  - Confidence: {fact['confidence']:.2f}")
            logger.info(f"  - Content preview: {fact['content'][:150]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Full integration test failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "🧪 TESTING DEEP RESEARCH INTEGRATION" + "\n")
    
    results = {
        "converter": test_converter(),
        "client": test_deepresearch_client(),
        "imports": test_integration_imports(),
        "retrieve_facts_mock": test_retrieve_facts_mock(),
    }
    
    # Only run full integration if client is available
    if results["client"]:
        results["full_integration"] = test_full_integration()
    else:
        logger.info("\n⏭️  Skipping full integration test (API not available)")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    total_pass = sum(results.values())
    total_tests = len(results)
    
    logger.info(f"\nTotal: {total_pass}/{total_tests} tests passed")
    
    if total_pass == total_tests:
        logger.info("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.info(f"\n⚠️  {total_tests - total_pass} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
