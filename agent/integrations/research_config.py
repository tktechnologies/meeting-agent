"""
Dynamic Deep Research Configuration

Automatically adjusts research parameters based on topic complexity,
user intent, and available time.

Author: TK Technologies
Version: 1.0.0
"""

import os
import re
from typing import Dict, Any, Optional
from enum import Enum


class TopicComplexity(Enum):
    """Topic complexity levels."""
    SIMPLE = "simple"        # Basic queries, status checks
    MODERATE = "moderate"    # Standard topics
    COMPLEX = "complex"      # Strategic, transformational topics
    CRITICAL = "critical"    # Decision-making, high-stakes


class ResearchConfig:
    """
    Smart configuration for Deep Research requests.
    
    Automatically determines optimal parameters based on:
    - Topic complexity
    - User intent
    - Available time budget
    - Historical performance
    """
    
    # Complexity detection keywords
    COMPLEX_KEYWORDS = [
        # Strategic
        "estratégia", "strategy", "strategic", "estratégica",
        "transformação", "transformation", "transformational",
        "inovação", "innovation", "innovative",
        "futuro", "future", "próximos anos",
        
        # Business critical
        "decisão", "decision", "escolha", "choice",
        "investimento", "investment", "orçamento", "budget",
        "risco", "risk", "ameaça", "threat",
        
        # Complex domains
        "arquitetura", "architecture", "infraestrutura",
        "inteligência artificial", "artificial intelligence", "ia", "ai",
        "machine learning", "deep learning", "quantum",
        "blockchain", "web3", "metaverso", "metaverse",
        
        # Organizational
        "reorganização", "reestruturação", "mudança cultural",
        "digital transformation", "transformação digital"
    ]
    
    MODERATE_KEYWORDS = [
        "projeto", "project", "iniciativa", "initiative",
        "processo", "process", "workflow",
        "produto", "product", "feature",
        "análise", "analysis", "review"
    ]
    
    SIMPLE_KEYWORDS = [
        "status", "update", "atualização",
        "resumo", "summary", "overview",
        "lista", "list", "check"
    ]
    
    # Intent-based configurations
    INTENT_CONFIGS = {
        "alignment": {
            "description": "Team alignment meeting",
            "min_steps": 3,
            "preferred_steps": 5,
            "max_steps": 7,
            "timeout": 180
        },
        "decision": {
            "description": "Decision-making meeting",
            "min_steps": 5,
            "preferred_steps": 7,
            "max_steps": 10,
            "timeout": 300
        },
        "status": {
            "description": "Status update meeting",
            "min_steps": 2,
            "preferred_steps": 3,
            "max_steps": 5,
            "timeout": 120
        },
        "brainstorm": {
            "description": "Brainstorming session",
            "min_steps": 3,
            "preferred_steps": 5,
            "max_steps": 7,
            "timeout": 180
        },
        "review": {
            "description": "Review meeting",
            "min_steps": 3,
            "preferred_steps": 4,
            "max_steps": 6,
            "timeout": 150
        }
    }
    
    def __init__(
        self,
        max_steps: Optional[int] = None,
        fallback_steps: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize research config.
        
        Args:
            max_steps: Override max steps (default from env, min 3)
            fallback_steps: Override fallback steps (default from env, min 3)
            timeout: Override timeout (default from env)
        """
        # Deep Research Agent requires min 3 steps
        self.max_steps = max(3, max_steps or int(os.environ.get("DEEPRESEARCH_MAX_STEPS", "5")))
        self.fallback_steps = max(3, fallback_steps or int(os.environ.get("DEEPRESEARCH_FALLBACK_STEPS", "3")))
        self.timeout = timeout or int(os.environ.get("DEEPRESEARCH_TIMEOUT", "300"))
    
    
    def detect_complexity(self, topic: str) -> TopicComplexity:
        """
        Detect topic complexity from text.
        
        Args:
            topic: Topic or query text
            
        Returns:
            TopicComplexity level
        """
        topic_lower = topic.lower()
        
        # Count keyword matches
        complex_matches = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in topic_lower)
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in topic_lower)
        simple_matches = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in topic_lower)
        
        # Check for critical indicators
        if any(word in topic_lower for word in ["decisão crítica", "urgente", "emergência"]):
            return TopicComplexity.CRITICAL
        
        # Determine complexity
        if complex_matches >= 2:
            return TopicComplexity.COMPLEX
        elif complex_matches >= 1 or moderate_matches >= 2:
            return TopicComplexity.MODERATE
        elif simple_matches >= 1:
            return TopicComplexity.SIMPLE
        else:
            # Default to moderate
            return TopicComplexity.MODERATE
    
    
    def get_optimal_config(
        self,
        topic: str,
        intent: str = "alignment",
        time_budget: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get optimal configuration for research request.
        
        Args:
            topic: Research topic
            intent: Meeting intent (alignment, decision, status, etc.)
            time_budget: Available time in seconds (optional)
            
        Returns:
            Dictionary with optimal configuration:
            {
                "max_steps": int,
                "fallback_steps": int,
                "timeout": int,
                "complexity": str,
                "reasoning": str
            }
        """
        # Detect complexity
        complexity = self.detect_complexity(topic)
        
        # Get intent config
        intent_config = self.INTENT_CONFIGS.get(intent, self.INTENT_CONFIGS["alignment"])
        
        # Determine optimal steps based on complexity and intent
        if complexity == TopicComplexity.CRITICAL:
            optimal_steps = min(self.max_steps, intent_config["max_steps"])
            fallback = min(self.fallback_steps, intent_config["preferred_steps"])
        elif complexity == TopicComplexity.COMPLEX:
            optimal_steps = min(self.max_steps, intent_config["preferred_steps"])
            fallback = min(self.fallback_steps, intent_config["min_steps"] + 1)
        elif complexity == TopicComplexity.MODERATE:
            optimal_steps = min(self.max_steps, intent_config["min_steps"] + 2)
            fallback = self.fallback_steps
        else:  # SIMPLE
            optimal_steps = min(self.max_steps, intent_config["min_steps"])
            fallback = self.fallback_steps
        
        # Ensure minimum 3 steps (Deep Research Agent requirement)
        optimal_steps = max(3, optimal_steps)
        fallback = max(3, fallback)
        
        # Adjust for time budget if provided
        if time_budget:
            # Rough estimate: ~30-40s per step
            max_steps_for_budget = max(3, time_budget // 40)  # Min 3 steps
            optimal_steps = min(optimal_steps, max_steps_for_budget)
            fallback = min(fallback, max(3, max_steps_for_budget // 2))  # Min 3 steps
        
        # Build reasoning
        reasoning_parts = [
            f"Complexidade: {complexity.value}",
            f"Intent: {intent}",
            f"Steps: {optimal_steps} (fallback: {fallback})"
        ]
        
        if time_budget:
            reasoning_parts.append(f"Time budget: {time_budget}s")
        
        return {
            "max_steps": optimal_steps,
            "fallback_steps": fallback,
            "timeout": time_budget or intent_config["timeout"],
            "complexity": complexity.value,
            "intent_description": intent_config["description"],
            "reasoning": " | ".join(reasoning_parts)
        }
    
    
    def should_use_deep_research(
        self,
        topic: str,
        internal_facts_count: int,
        intent: str = "alignment"
    ) -> Dict[str, Any]:
        """
        Determine if Deep Research should be used.
        
        Args:
            topic: Research topic
            internal_facts_count: Number of facts already retrieved
            intent: Meeting intent
            
        Returns:
            {
                "should_use": bool,
                "reason": str,
                "config": dict (if should_use=True)
            }
        """
        # Always use for critical topics
        complexity = self.detect_complexity(topic)
        if complexity == TopicComplexity.CRITICAL:
            return {
                "should_use": True,
                "reason": "Tópico crítico - Deep Research obrigatório",
                "config": self.get_optimal_config(topic, intent)
            }
        
        # Use if few internal facts
        if internal_facts_count < 8:
            return {
                "should_use": True,
                "reason": f"Poucos facts internos ({internal_facts_count}) - Deep Research recomendado",
                "config": self.get_optimal_config(topic, intent)
            }
        
        # Use for complex topics even with some facts
        if complexity == TopicComplexity.COMPLEX and internal_facts_count < 15:
            return {
                "should_use": True,
                "reason": f"Tópico complexo - Deep Research para aprofundar ({internal_facts_count} facts existentes)",
                "config": self.get_optimal_config(topic, intent)
            }
        
        # Don't use - enough facts
        return {
            "should_use": False,
            "reason": f"Facts suficientes ({internal_facts_count}) para tópico {complexity.value}"
        }


# Convenience function
def get_research_config(
    topic: str,
    intent: str = "alignment",
    internal_facts_count: int = 0,
    time_budget: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get optimal Deep Research configuration.
    
    Args:
        topic: Research topic
        intent: Meeting intent
        internal_facts_count: Number of facts already retrieved
        time_budget: Available time in seconds
        
    Returns:
        Complete configuration with decision
    """
    config = ResearchConfig()
    
    decision = config.should_use_deep_research(topic, internal_facts_count, intent)
    
    if decision["should_use"]:
        optimal_config = config.get_optimal_config(topic, intent, time_budget)
        decision["config"] = optimal_config
    
    return decision
