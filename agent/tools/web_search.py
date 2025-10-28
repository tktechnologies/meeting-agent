"""
Web search tool using the internal Deep Research Agent.

This tool allows the meeting agent to search the web for current information
about companies, topics, or any context needed for agenda planning.

Based on chat-agent's search-service.js.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# --- PASSO 1: IMPORTAÇÃO ADICIONADA ---
from agent.integrations.deepresearch_client import quick_research, DeepResearchError

# ------------------------------------

# Try to import httpx (async HTTP client)
# (Este bloco não é mais usado pela ferramenta, mas pode ser mantido)
try:
    import httpx
    HAVE_HTTPX = True
except ImportError:
    HAVE_HTTPX = False
    logger.warning("httpx not installed - web search will be unavailable")


async def perform_web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    days: int = 30,
) -> Dict[str, Any]:
    """
    Perform web search using Tavily API. (FUNÇÃO ANTIGA - NÃO UTILIZADA)
    
    Args:
        query: Search query (e.g., "BYD electric vehicles latest news")
        max_results: Maximum number of results to return (default: 5)
        search_depth: "basic" or "advanced" (default: basic for speed)
        days: Number of days to look back for results (default: 30)
    
    Returns:
        Dictionary with:
        - success: bool
        - results: List of search results
        - formatted_summary: Human-readable summary
        - references: List of sources
    """
    if not HAVE_HTTPX:
        return {
            "success": False,
            "error": "httpx not installed - run: pip install httpx",
            "results": [],
            "formatted_summary": "",
            "references": []
        }
    
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    
    if not tavily_api_key:
        logger.warning("TAVILY_API_KEY not configured - web search disabled")
        return {
            "success": False,
            "error": "TAVILY_API_KEY not configured in .env",
            "results": [],
            "formatted_summary": f"Web search attempted for: '{query}' but API key not configured.",
            "references": []
        }
    
    try:
        logger.info(f"🔍 Searching web for: '{query}' (max_results={max_results}, depth={search_depth})")
        
        # Build search parameters
        search_params = {
            "api_key": tavily_api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": True,
            "max_results": max_results,
            "include_raw_content": False,  # Don't need full HTML
        }
        
        if days and days > 0:
            search_params["days"] = days
        
        # Perform search with timeout
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json=search_params,
                headers={"Content-Type": "application/json"}
            )
            
        if not response.is_success:
                error_text = response.text
                logger.error(f"Tavily API error: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "error": f"Tavily API error: {response.status_code}",
                    "results": [],
                    "formatted_summary": "",
                    "references": []
                }
            
        data = response.json()
        
        # Format results
        results = data.get("results", [])
        answer = data.get("answer", "")
        
        logger.info(f"✅ Search successful - found {len(results)} results")
        
        # Create formatted summary for LLM
        formatted_summary = _format_search_results(query, answer, results)
        
        # Extract references
        references = _extract_references(results)
        
        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results,
            "answer": answer,
            "formatted_summary": formatted_summary,
            "references": references,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "search_depth": search_depth,
                "max_results": max_results,
                "days": days
            }
        }
        
    except httpx.TimeoutException:
        logger.error(f"Search timeout for query: {query}")
        return {
            "success": False,
            "error": "Search request timed out",
            "results": [],
            "formatted_summary": "",
            "references": []
        }
    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "results": [],
            "formatted_summary": "",
            "references": []
        }


def _format_search_results(query: str, answer: str, results: List[Dict]) -> str:
    """Format search results into a summary for the LLM. (FUNÇÃO ANTIGA - NÃO UTILIZADA)"""
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    formatted = f"=== WEB SEARCH RESULTS ===\n"
    formatted += f"Query: '{query}'\n"
    formatted += f"Search Date: {current_date}\n\n"
    
    if answer:
        formatted += f"📌 SUMMARY:\n{answer}\n\n"
    
    if results:
        formatted += f"📰 SOURCES ({len(results)} found):\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result.get('title', 'No title')}\n"
            formatted += f"   URL: {result.get('url', 'N/A')}\n"
            if result.get('published_date'):
                formatted += f"   Published: {result['published_date']}\n"
            content = result.get('content', '')
            if content:
                # Truncate long content
                content_preview = content[:300] + "..." if len(content) > 300 else content
                formatted += f"   Content: {content_preview}\n"
            formatted += "\n"
    else:
        formatted += "⚠️ No specific sources found.\n\n"
    
    formatted += "=== END SEARCH RESULTS ===\n"
    
    return formatted


def _extract_references(results: List[Dict]) -> List[Dict[str, str]]:
    """Extract clean references for citations. (FUNÇÃO ANTIGA - NÃO UTILIZADA)"""
    references = []
    
    for i, result in enumerate(results, 1):
        url = result.get('url', '')
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname if url else 'unknown'
        except:
            domain = 'unknown'
        
        references.append({
            "id": i,
            "title": result.get('title', 'No title'),
            "url": url,
            "published_date": result.get('published_date'),
            "domain": domain
        })
    
    return references

# --- PASSO 2: FUNÇÃO SUBSTITUÍDA ---
def search_for_context(
    query: str,
    **kwargs  # Captura argumentos extras (como max_results) que não usaremos
) -> str:
    """
    Wrapper síncrono para o Deep Research Client.
    Retorna o relatório da pesquisa como uma string.
    """
    logger.info(f"Iniciando 'quick_research' (síncrona) para: {query}")
    try:
        # Chama diretamente a função do seu cliente
        report = quick_research(
            topic=query,
            model_provider="gemini"  # Definindo 'gemini' como padrão
        )
        
        if not report:
             logger.warning(f"Pesquisa para '{query}' retornou um relatório vazio.")
             return "A pesquisa foi bem-sucedida, mas não produziu um relatório."
        
        logger.info(f"Pesquisa para '{query}' concluída, retornando relatório.")
        return report
        
    except DeepResearchError as e:
        logger.error(f"Erro na 'quick_research' para '{query}': {e}")
        return f"A pesquisa falhou com o erro: {e}"
    
    except Exception as e:
        logger.error(f"Erro inesperado na 'quick_research' para '{query}': {e}")
        return f"A pesquisa falhou com um erro inesperado: {e}"

# --- PASSO 3: FERRAMENTA SUBSTITUÍDA ---
try:
    from langchain.tools import Tool
    
    web_search_tool = Tool(
        name="deep_research",  # Nome mais claro
        description=(
            "Use esta ferramenta para realizar pesquisas aprofundadas sobre um tópico específico. "
            "É ideal para quando você precisa de informações detalhadas, análises de mercado, "
            "ou dados para embasar um planejamento estratégico para uma reunião. "
            "Forneça apenas o tópico da pesquisa como entrada (query)."
        ),
        func=search_for_context  # Continua usando a função que você acabou de modificar
    )
    
except ImportError:
    web_search_tool = None
    logger.debug("LangChain not available - web_search_tool not created")