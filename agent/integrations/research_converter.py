"""
Deep Research Result Converter
Converts Deep Research API results into Meeting Agent facts format.
"""

import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


def convert_research_to_facts(
    research_result: Dict[str, Any],
    org_id: str,
    query: str,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convert Deep Research result into Meeting Agent facts.
    
    Deep Research returns:
        - report: str (Markdown formatted research report)
        - plan: List[str] (research plan steps)
        - steps_completed: int
        - quality_scores: List[float] (quality per step)
        - avg_quality: float (0-10 average quality)
        - execution_time: float
        - model_provider: str
        - timestamp: str (ISO format)
        - correlation_id: Optional[str]
    
    Meeting Agent expects facts:
        - fact_id: str (unique identifier)
        - fact_type: str (category of fact)
        - org_id: str (organization identifier)
        - content: str (main text content)
        - payload: Dict (additional structured data)
        - confidence: float (0-1 confidence score)
        - source: str (origin of fact)
        - status: str (published, draft, archived)
        - created_at: str (ISO timestamp)
        - metadata: Dict (additional info)
    
    Args:
        research_result: Result from Deep Research API
        org_id: Organization identifier
        query: Original research query
        user_id: Optional user who requested research
        
    Returns:
        List of facts in Meeting Agent format
    """
    facts = []
    
    try:
        # Extract data from research result
        report = research_result.get("report", "")
        plan = research_result.get("plan", [])
        steps_completed = research_result.get("steps_completed", 0)
        quality_scores = research_result.get("quality_scores", [])
        avg_quality = research_result.get("avg_quality", 0.0)
        execution_time = research_result.get("execution_time", 0.0)
        model_provider = research_result.get("model_provider", "unknown")
        timestamp = research_result.get("timestamp", datetime.utcnow().isoformat())
        correlation_id = research_result.get("correlation_id")
        
        # Generate unique fact_id based on query and timestamp
        fact_id_hash = hashlib.sha256(
            f"{query}_{timestamp}_{org_id}".encode()
        ).hexdigest()[:16]
        fact_id = f"deepresearch_{fact_id_hash}"
        
        # Convert quality score (0-10) to confidence (0-1)
        confidence = min(max(avg_quality / 10.0, 0.0), 1.0)
        
        # Extract summary and key findings
        summary = _extract_summary_from_report(report) if report else ""
        key_findings = _extract_key_findings_from_report(report) if report else []
        
        # If report is empty or very short, create summary from plan
        if not summary or len(summary) < 50:
            if plan:
                summary = f"Deep Research Analysis: {query}\n\nResearch Plan:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
            else:
                summary = f"Deep Research Analysis: {query}\n\nResearch completed with {steps_completed} steps and quality score of {avg_quality:.1f}/10."
        
        # Create main fact with full report
        main_fact = {
            "fact_id": fact_id,
            "fact_type": "deep_research_report",
            "org_id": org_id,
            "content": summary,  # Use summary as main content
            "payload": {
                "title": f"Deep Research: {query[:100]}",
                "query": query,
                "report": report,
                "summary": summary,
                "key_findings": key_findings,
                "plan": plan,
                "model_provider": model_provider,
                "search_provider": "tavily"
            },
            "confidence": confidence,
            "source": "deep_research_agent",
            "status": "published",
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": {
                "steps_completed": steps_completed,
                "quality_scores": quality_scores,
                "avg_quality": avg_quality,
                "execution_time": execution_time,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "research_depth": "deep" if steps_completed >= 7 else "standard"
            }
        }
        
        facts.append(main_fact)
        
        # Optional: Create individual facts for each section
        section_facts = _extract_section_facts(
            report=report,
            base_fact_id=fact_id,
            org_id=org_id,
            query=query,
            confidence=confidence,
            timestamp=timestamp
        )
        
        facts.extend(section_facts)
        
        logger.info(
            f"Converted research to {len(facts)} facts",
            extra={
                "query": query[:100],
                "org_id": org_id,
                "facts_count": len(facts),
                "avg_quality": avg_quality,
                "correlation_id": correlation_id
            }
        )
        
        return facts
        
    except Exception as e:
        logger.exception(
            "Failed to convert research to facts",
            extra={
                "query": query,
                "org_id": org_id
            }
        )
        # Return empty list on error (graceful degradation)
        return []


def _extract_summary_from_report(report: str) -> str:
    """
    Extract summary section from Markdown report.
    
    Looks for common summary patterns:
    - ## Summary
    - ## Executive Summary
    - ## Key Takeaways
    - ## Overview
    
    Args:
        report: Full Markdown report
        
    Returns:
        Summary text or first 500 chars if no summary found
    """
    summary_headers = [
        "## Summary",
        "## Executive Summary", 
        "## Key Takeaways",
        "## Overview",
        "## Resumo",
        "## Resumo Executivo"
    ]
    
    for header in summary_headers:
        if header in report:
            # Extract text after header until next ## or end
            start_idx = report.index(header) + len(header)
            rest = report[start_idx:]
            
            # Find next section
            next_section = rest.find("\n## ")
            if next_section != -1:
                return rest[:next_section].strip()
            else:
                return rest[:500].strip()
    
    # Fallback: return first 500 chars
    return report[:500].strip() + "..."


def _extract_key_findings_from_report(report: str) -> List[str]:
    """
    Extract bullet points or numbered findings from report.
    
    Args:
        report: Full Markdown report
        
    Returns:
        List of key finding strings
    """
    findings = []
    lines = report.split("\n")
    
    for line in lines:
        line = line.strip()
        # Look for bullet points or numbered lists
        if line.startswith("- ") or line.startswith("* "):
            findings.append(line[2:].strip())
        elif len(line) > 3 and line[0].isdigit() and line[1:3] in [". ", ") "]:
            findings.append(line[3:].strip())
    
    # Return top 10 findings
    return findings[:10]


def _extract_section_facts(
    report: str,
    base_fact_id: str,
    org_id: str,
    query: str,
    confidence: float,
    timestamp: str
) -> List[Dict[str, Any]]:
    """
    Extract individual sections from report as separate facts.
    
    This allows for more granular fact retrieval and better context.
    
    Args:
        report: Full Markdown report
        base_fact_id: Base fact ID to derive section IDs
        org_id: Organization ID
        query: Original query
        confidence: Confidence score
        timestamp: Creation timestamp
        
    Returns:
        List of section facts
    """
    section_facts = []
    
    # Split by ## headers
    sections = report.split("\n## ")
    
    for idx, section in enumerate(sections[1:], start=1):  # Skip first (before any ##)
        if not section.strip():
            continue
            
        # Extract section title (first line)
        lines = section.split("\n", 1)
        section_title = lines[0].strip()
        section_content = lines[1] if len(lines) > 1 else ""
        
        if len(section_content.strip()) < 50:  # Skip tiny sections
            continue
        
        section_fact_id = f"{base_fact_id}_section_{idx}"
        
        section_fact = {
            "fact_id": section_fact_id,
            "fact_type": "deep_research_section",
            "org_id": org_id,
            "content": section_content.strip()[:500],  # First 500 chars as content
            "payload": {
                "title": section_title,
                "full_content": section_content.strip(),
                "query": query,
                "section_number": idx,
                "parent_fact_id": base_fact_id
            },
            "confidence": confidence,
            "source": "deep_research_agent",
            "status": "published",
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": {
                "section_title": section_title,
                "section_type": _classify_section_type(section_title)
            }
        }
        
        section_facts.append(section_fact)
    
    return section_facts


def _classify_section_type(section_title: str) -> str:
    """
    Classify section type based on title.
    
    Args:
        section_title: Section header text
        
    Returns:
        Section type classification
    """
    title_lower = section_title.lower()
    
    if any(word in title_lower for word in ["summary", "overview", "introduction", "resumo", "visão geral"]):
        return "summary"
    elif any(word in title_lower for word in ["finding", "result", "discovery", "achado", "resultado"]):
        return "findings"
    elif any(word in title_lower for word in ["analysis", "deep dive", "investigation", "análise", "investigação"]):
        return "analysis"
    elif any(word in title_lower for word in ["conclusion", "recommendation", "next steps", "conclusão", "recomendação"]):
        return "conclusion"
    elif any(word in title_lower for word in ["background", "context", "history", "contexto", "histórico"]):
        return "background"
    else:
        return "general"


def validate_research_result(research_result: Dict[str, Any]) -> bool:
    """
    Validate that research result has required fields.
    
    Args:
        research_result: Result from Deep Research API
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ["steps_completed", "avg_quality"]
    
    for field in required_fields:
        if field not in research_result:
            logger.warning(f"Missing required field in research result: {field}")
            return False
    
    # Validate quality score is reasonable (lowered threshold to 3.0)
    if research_result["avg_quality"] < 3.0:
        logger.warning(f"Research quality too low: {research_result['avg_quality']}")
        return False
    
    # Validate at least some steps were completed
    if research_result["steps_completed"] < 1:
        logger.warning("No research steps completed")
        return False
    
    return True
