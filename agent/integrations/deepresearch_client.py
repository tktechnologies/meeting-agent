"""
Deep Research Agent Integration Client

HTTP client for consuming the Deep Research Agent API.
Provides sync/async research capabilities with automatic retry and circuit breaking.

Author: TK Technologies
Version: 1.0.0
"""

import os
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)

logger = logging.getLogger(__name__)


class DeepResearchError(Exception):
    """Base exception for Deep Research client errors."""
    pass


class DeepResearchTimeoutError(DeepResearchError):
    """Raised when a research request times out."""
    pass


class DeepResearchUnavailableError(DeepResearchError):
    """Raised when Deep Research Agent is unavailable."""
    pass


class DeepResearchClient:
    """
    Client for Deep Research Agent API.
    
    Features:
    - Automatic retry with exponential backoff
    - Circuit breaker pattern
    - Sync and async research modes
    - Health monitoring
    - Correlation ID propagation for distributed tracing
    
    Example:
        >>> client = DeepResearchClient("http://localhost:8000")
        >>> result = client.research_sync("AI in Healthcare", correlation_id="req-123")
        >>> print(result['report'])
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
        api_key: Optional[str] = None
    ):
        """
        Initialize Deep Research client.
        
        Args:
            base_url: Base URL of Deep Research Agent API
                     (default: DEEPRESEARCH_API_URL env var or http://localhost:8000)
            timeout: Request timeout in seconds (default: 300)
            max_retries: Maximum retry attempts (default: 3)
            api_key: Optional API key for authentication
        """
        self.base_url = (
            base_url or
            os.getenv("DEEPRESEARCH_API_URL", "http://localhost:8000")
        ).rstrip('/')
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = api_key
        
        # Create HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100
            ),
            http2=True  # Enable HTTP/2 for better performance
        )
        
        # Circuit breaker state
        self._failure_count = 0
        self._last_failure_time = None
        self._circuit_open = False
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60.0
        
        logger.info(f"DeepResearchClient initialized: {self.base_url}")
    
    def __del__(self):
        """Clean up HTTP client on destruction."""
        try:
            self.client.close()
        except:
            pass
    
    def _check_circuit_breaker(self) -> None:
        """
        Check circuit breaker state.
        
        Circuit breaker pattern:
        - Opens after N consecutive failures
        - Stays open for M seconds
        - Attempts recovery after timeout
        
        Raises:
            DeepResearchUnavailableError: If circuit is open
        """
        if not self._circuit_open:
            return
        
        # Check if timeout elapsed
        if self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed > self._circuit_breaker_timeout:
                logger.info("Circuit breaker: attempting recovery")
                self._circuit_open = False
                self._failure_count = 0
                return
        
        raise DeepResearchUnavailableError(
            f"Deep Research Agent circuit breaker is OPEN. "
            f"Service unavailable after {self._failure_count} failures. "
            f"Retry after {self._circuit_breaker_timeout}s."
        )
    
    def _record_success(self) -> None:
        """Record successful request (reset circuit breaker)."""
        self._failure_count = 0
        self._circuit_open = False
        self._last_failure_time = None
    
    def _record_failure(self) -> None:
        """Record failed request (update circuit breaker)."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self._circuit_breaker_threshold:
            self._circuit_open = True
            logger.error(
                f"Circuit breaker OPENED after {self._failure_count} failures. "
                f"Deep Research Agent unavailable for {self._circuit_breaker_timeout}s."
            )
    
    def _build_headers(self, correlation_id: Optional[str] = None) -> Dict[str, str]:
        """Build HTTP headers with optional correlation ID."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MeetingAgent/1.0 (DeepResearchClient)"
        }
        
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
            headers["X-Request-ID"] = correlation_id
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    def health_check(self) -> bool:
        """
        Check if Deep Research Agent is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = self.client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "healthy"
            
            return False
            
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def research_sync(
        self,
        topic: str,
        model_provider: str = "openai",
        max_steps: int = 5,
        correlation_id: Optional[str] = None,
        interactive: bool = False
    ) -> Dict[str, Any]:
        """
        Execute synchronous research.
        
        Use for quick research that completes in < 5 minutes.
        
        Args:
            topic: Research topic/question
            model_provider: "openai" (GPT-5, default), "gemini" or "anthropic"
            max_steps: Maximum research steps (3-10)
            correlation_id: Optional correlation ID for tracing
            interactive: Enable human-in-the-loop (not recommended for integration)
        
        Returns:
            {
                'report': str,              # Markdown report
                'steps_completed': int,     # Number of steps executed
                'quality_scores': [float],  # Quality scores per step
                'avg_quality': float,       # Average quality (0-10)
                'execution_time': float,    # Execution time in seconds
                'plan': [str],              # Research plan steps
                'model_provider': str       # Model used
            }
        
        Raises:
            DeepResearchTimeoutError: If request times out
            DeepResearchUnavailableError: If service is unavailable
            DeepResearchError: For other errors
        """
        # Check circuit breaker
        self._check_circuit_breaker()
        
        # Prepare request
        payload = {
            "topic": topic,
            "model_provider": model_provider,
            "max_steps": max_steps,
            "interactive": interactive
        }
        
        headers = self._build_headers(correlation_id)
        
        logger.info(
            f"Deep Research sync request: topic='{topic[:50]}...', "
            f"provider={model_provider}, max_steps={max_steps}"
        )
        
        start_time = time.time()
        
        try:
            response = self.client.post(
                f"{self.base_url}/research",
                json=payload,
                headers=headers
            )
            
            response.raise_for_status()
            
            result = response.json()
            
            execution_time = time.time() - start_time
            
            logger.info(
                f"Deep Research sync completed: "
                f"quality={result.get('avg_quality', 0):.1f}/10, "
                f"steps={result.get('steps_completed', 0)}, "
                f"time={execution_time:.1f}s"
            )
            
            # Record success
            self._record_success()
            
            return result
        
        except httpx.TimeoutException as e:
            self._record_failure()
            logger.error(f"Deep Research timeout: {e}")
            raise DeepResearchTimeoutError(
                f"Research timed out after {self.timeout}s"
            ) from e
        
        except httpx.HTTPStatusError as e:
            self._record_failure()
            logger.error(
                f"Deep Research HTTP error: {e.response.status_code} - {e.response.text}"
            )
            raise DeepResearchError(
                f"HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        
        except Exception as e:
            self._record_failure()
            logger.error(f"Deep Research unexpected error: {e}")
            raise DeepResearchError(f"Unexpected error: {e}") from e
    
    def research_async_start(
        self,
        topic: str,
        model_provider: str = "openai",
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Start asynchronous research (returns job ID).
        
        Use for complex research that may take > 5 minutes.
        
        Args:
            topic: Research topic/question
            model_provider: "openai" (GPT-5, default), "gemini" or "anthropic"
            correlation_id: Optional correlation ID for tracing
        
        Returns:
            job_id: Job identifier for status checking
        
        Raises:
            DeepResearchUnavailableError: If service is unavailable
            DeepResearchError: For other errors
        """
        # Check circuit breaker
        self._check_circuit_breaker()
        
        payload = {
            "topic": topic,
            "model_provider": model_provider
        }
        
        headers = self._build_headers(correlation_id)
        
        logger.info(f"Starting async research: topic='{topic[:50]}...', provider={model_provider}")
        
        try:
            response = self.client.post(
                f"{self.base_url}/research/async",
                json=payload,
                headers=headers,
                timeout=30.0  # Short timeout for job creation
            )
            
            response.raise_for_status()
            
            result = response.json()
            job_id = result["job_id"]
            
            logger.info(f"Async research started: job_id={job_id}")
            
            self._record_success()
            
            return job_id
        
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to start async research: {e}")
            raise DeepResearchError(f"Failed to start async research: {e}") from e
    
    def research_async_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check status of asynchronous research job.
        
        Args:
            job_id: Job identifier from research_async_start()
        
        Returns:
            {
                'job_id': str,
                'status': str,  # 'queued', 'processing', 'completed', 'failed'
                'result': dict or None,  # Available when status='completed'
                'error': str or None,    # Available when status='failed'
                'progress': int or None  # 0-100%
            }
        
        Raises:
            DeepResearchError: If job not found or other error
        """
        try:
            response = self.client.get(
                f"{self.base_url}/research/{job_id}",
                timeout=10.0
            )
            
            response.raise_for_status()
            
            return response.json()
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise DeepResearchError(f"Job not found: {job_id}") from e
            raise DeepResearchError(f"Failed to get job status: {e}") from e
        
        except Exception as e:
            logger.error(f"Error checking job status: {e}")
            raise DeepResearchError(f"Error checking job status: {e}") from e
    
    def research_async_wait(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0
    ) -> Dict[str, Any]:
        """
        Wait for asynchronous research to complete (blocking).
        
        Polls job status until completion or timeout.
        
        Args:
            job_id: Job identifier
            poll_interval: Seconds between status checks (default: 5)
            max_wait: Maximum wait time in seconds (default: 600 = 10 min)
        
        Returns:
            Research result (same format as research_sync)
        
        Raises:
            DeepResearchTimeoutError: If max_wait exceeded
            DeepResearchError: If job failed or other error
        """
        start_time = time.time()
        
        logger.info(f"Waiting for async job {job_id} (max {max_wait}s)...")
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > max_wait:
                raise DeepResearchTimeoutError(
                    f"Job {job_id} did not complete within {max_wait}s"
                )
            
            status = self.research_async_status(job_id)
            
            if status["status"] == "completed":
                logger.info(f"Job {job_id} completed successfully")
                return status["result"]
            
            elif status["status"] == "failed":
                error = status.get("error", "Unknown error")
                logger.error(f"Job {job_id} failed: {error}")
                raise DeepResearchError(f"Job failed: {error}")
            
            # Still processing, wait and retry
            logger.debug(f"Job {job_id} status: {status['status']}, elapsed: {elapsed:.1f}s")
            time.sleep(poll_interval)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get Deep Research Agent metrics.
        
        Returns:
            {
                'total_requests': int,
                'successful_requests': int,
                'failed_requests': int,
                'avg_execution_time': float,
                'cache_hit_rate': float,
                'uptime_seconds': float
            }
        """
        try:
            response = self.client.get(
                f"{self.base_url}/metrics",
                timeout=5.0
            )
            
            response.raise_for_status()
            
            return response.json()
        
        except Exception as e:
            logger.warning(f"Failed to get metrics: {e}")
            return {}


# Convenience function for quick usage
def quick_research(
    topic: str,
    base_url: Optional[str] = None,
    model_provider: str = "openai",
    timeout: float = 300.0
) -> str:
    """
    Quick research helper (returns report text only).
    
    Example:
        >>> report = quick_research("What is Quantum Computing?")
        >>> print(report)
    
    Args:
        topic: Research topic
        base_url: Optional Deep Research Agent URL
        model_provider: "openai" (GPT-5, default), "gemini" or "anthropic"
        timeout: Timeout in seconds
    
    Returns:
        Markdown report text
    """
    client = DeepResearchClient(base_url=base_url, timeout=timeout)
    result = client.research_sync(topic, model_provider=model_provider)
    return result['report']
