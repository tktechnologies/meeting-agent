"""
Debug script to inspect Deep Research API response
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agent.integrations.deepresearch_client import DeepResearchClient

def debug_response():
    """Inspect the actual API response structure"""
    
    base_url = os.environ.get(
        "DEEPRESEARCH_BASE_URL",
        "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io"
    )
    
    client = DeepResearchClient(base_url=base_url)
    
    logger.info("Executing simple research to inspect response...")
    
    result = client.research_sync(
        topic="AI trends 2025",
        model_provider="openai",
        max_steps=3,  # Minimum is 3
        correlation_id="debug-test"
    )
    
    logger.info("\n" + "="*80)
    logger.info("FULL API RESPONSE")
    logger.info("="*80)
    logger.info(json.dumps(result, indent=2, ensure_ascii=False))
    
    logger.info("\n" + "="*80)
    logger.info("RESPONSE KEYS")
    logger.info("="*80)
    for key in result.keys():
        value = result[key]
        value_type = type(value).__name__
        if isinstance(value, str):
            preview = value[:100] if len(value) > 100 else value
            logger.info(f"{key}: {value_type} - '{preview}'")
        elif isinstance(value, list):
            logger.info(f"{key}: {value_type} - {len(value)} items")
        else:
            logger.info(f"{key}: {value_type} - {value}")

if __name__ == "__main__":
    debug_response()
