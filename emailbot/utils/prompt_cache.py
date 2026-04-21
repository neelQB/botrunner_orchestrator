"""
Prompt Cache Utilities - Monitoring and helpers for OpenAI automatic prompt caching.

OpenAI automatically caches prompt prefixes >= 1024 tokens (GPT-4o/4.1) or
>= 2048 tokens (other models). Cached tokens are billed at 50% of input cost.

This module provides:
- CACHE_BREAK marker for prompt segmentation (static/dynamic split)
- PromptCacheMonitor for tracking cache hit rates and cost savings
- Helper functions for prompt splitting and message construction

Strategy:
    1. Each prompt inserts CACHE_BREAK between static instructions and dynamic context
    2. RouterModel splits system instructions on CACHE_BREAK into two system messages
    3. The first system message (static) gets cached automatically by OpenAI/Azure
    4. The second system message (dynamic) contains per-request data

Usage:
    from emailbot.utils.prompt_cache import CACHE_BREAK, cache_monitor, split_cached_prompt
    
    # In prompt functions:
    prompt = f"{static_instructions}{CACHE_BREAK}{dynamic_context}"
    
    # In RouterModel:
    static, dynamic = split_cached_prompt(system_instructions)
    
    # Monitor cache performance:
    cache_monitor.record(response, model="primary")
    stats = cache_monitor.get_stats()
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


from emailbot.config.settings import logger


# =============================================================================
# CACHE BREAK MARKER
# =============================================================================

CACHE_BREAK = "\n\n<!-- CACHE_BREAK -->\n\n"
"""
Marker inserted between static and dynamic parts of prompts.

The RouterModel splits system instructions on this marker to create
two system messages, maximizing OpenAI's automatic prefix caching.

- Static content (before marker): Role definitions, rules, examples, output format
- Dynamic content (after marker): User query, chat history, session state, scores

For caching to work, the static prefix must be >= 1024 tokens and identical
across requests for the same tenant/persona.
"""


# =============================================================================
# PROMPT SPLITTING
# =============================================================================


def split_cached_prompt(instructions: str) -> Tuple[str, Optional[str]]:
    """
    Split instructions on CACHE_BREAK marker into static and dynamic parts.

    Args:
        instructions: Full instruction string potentially containing CACHE_BREAK

    Returns:
        Tuple of (static_part, dynamic_part).
        If no marker found, returns (instructions, None).
    """
    if CACHE_BREAK in instructions:
        parts = instructions.split(CACHE_BREAK, 1)
        static = parts[0].strip()
        dynamic = parts[1].strip() if len(parts) > 1 else None
        return static, dynamic
    return instructions, None


def build_cached_messages(
    system_instructions: str,
    existing_messages: List[Dict[str, str]],
    enable_caching: bool = True,
) -> List[Dict[str, str]]:
    """
    Build message list with cache-optimized system message splitting.

    When caching is enabled and CACHE_BREAK is present, creates two system
    messages: static prefix (cached by OpenAI) + dynamic context.

    Args:
        system_instructions: Full system instructions string
        existing_messages: Existing conversation messages
        enable_caching: Whether to split for caching optimization

    Returns:
        Complete message list with system messages prepended
    """
    messages = list(existing_messages)

    if not system_instructions:
        return messages

    if enable_caching:
        static_part, dynamic_part = split_cached_prompt(system_instructions)
        if dynamic_part:
            # Insert dynamic part first (will be at index 0), then static
            # so final order is: [static, dynamic, ...conversation]
            messages.insert(0, {"role": "system", "content": dynamic_part})
            messages.insert(0, {"role": "system", "content": static_part})
            logger.debug(
                f"[PROMPT_CACHE] Split system prompt: "
                f"static={len(static_part)} chars, dynamic={len(dynamic_part)} chars"
            )
            return messages

    # No caching or no marker - single system message
    messages.insert(0, {"role": "system", "content": system_instructions})
    return messages


def split_direct_call_messages(
    system_content: str,
    enable_caching: bool = True,
) -> List[Dict[str, str]]:
    """
    Build system message list for direct router.acompletion calls.

    Used by summarizer.py and executive_summary.py which call
    router.acompletion() directly instead of through the Agents SDK.

    Args:
        system_content: System prompt content
        enable_caching: Whether to split for caching

    Returns:
        List of system message dicts
    """
    if enable_caching:
        static_part, dynamic_part = split_cached_prompt(system_content)
        if dynamic_part:
            return [
                {"role": "system", "content": static_part},
                {"role": "system", "content": dynamic_part},
            ]

    return [{"role": "system", "content": system_content}]


# =============================================================================
# CACHE MONITORING
# =============================================================================


@dataclass
class CacheStats:
    """Statistics for a single LLM request."""

    timestamp: float
    model: str
    total_prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    cache_hit: bool
    cache_hit_rate: float  # cached_tokens / total_prompt_tokens * 100
    estimated_savings_pct: float  # cost savings percentage


class PromptCacheMonitor:
    """
    Monitor and track prompt cache statistics across all LLM calls.

    Thread-safe monitoring of OpenAI's automatic prompt caching.
    Tracks cache hit rates, token savings, and cost reduction.

    OpenAI returns cached token counts in:
        response.usage.prompt_tokens_details.cached_tokens

    Azure OpenAI returns cached token counts similarly with
    API version >= 2024-10-01-preview.
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize the cache monitor.

        Args:
            max_history: Maximum number of request stats to retain
        """
        self._lock = threading.Lock()
        self._history: List[CacheStats] = []
        self._max_history = max_history
        self._total_requests = 0
        self._total_prompt_tokens = 0
        self._total_cached_tokens = 0
        self._total_completion_tokens = 0

    def record(self, response: Any, model: str = "unknown") -> Optional[CacheStats]:
        """
        Record cache statistics from an LLM response.

        Extracts cached token counts from the response's usage field.
        Works with both OpenAI and Azure OpenAI responses via LiteLLM.

        Args:
            response: LLM response object (LiteLLM ModelResponse)
            model: Model name for tracking

        Returns:
            CacheStats if usage data available, None otherwise
        """
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                return None

            total_prompt = getattr(usage, "prompt_tokens", 0) or 0
            completion = getattr(usage, "completion_tokens", 0) or 0

            # Extract cached tokens - OpenAI style
            cached = 0
            prompt_details = getattr(usage, "prompt_tokens_details", None)
            if prompt_details:
                cached = getattr(prompt_details, "cached_tokens", 0) or 0

            # Fallback: check cache_read_input_tokens (Anthropic/other providers)
            if cached == 0:
                cache_read = getattr(usage, "cache_read_input_tokens", 0)
                if cache_read:
                    cached = cache_read

            # Also check _cache_read_input_tokens (LiteLLM internal)
            if cached == 0:
                cache_read_alt = getattr(usage, "_cache_read_input_tokens", 0)
                if cache_read_alt:
                    cached = cache_read_alt

            cache_hit = cached > 0
            hit_rate = (cached / total_prompt * 100) if total_prompt > 0 else 0.0
            # Cached tokens cost 50% less: savings = (cached * 0.5) / total * 100
            savings = (cached * 50.0 / total_prompt) if total_prompt > 0 else 0.0

            stats = CacheStats(
                timestamp=time.time(),
                model=model,
                total_prompt_tokens=total_prompt,
                cached_tokens=cached,
                completion_tokens=completion,
                cache_hit=cache_hit,
                cache_hit_rate=hit_rate,
                estimated_savings_pct=savings,
            )

            with self._lock:
                self._total_requests += 1
                self._total_prompt_tokens += total_prompt
                self._total_cached_tokens += cached
                self._total_completion_tokens += completion
                self._history.append(stats)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history :]

            # Log cache info
            if cache_hit:
                logger.info(
                    f"[PROMPT_CACHE] HIT | model={model} | "
                    f"cached={cached}/{total_prompt} tokens ({hit_rate:.1f}%) | "
                    f"savings={savings:.1f}%"
                )
            else:
                logger.debug(
                    f"[PROMPT_CACHE] MISS | model={model} | "
                    f"prompt_tokens={total_prompt} | no cached tokens"
                )

            return stats

        except Exception as e:
            logger.debug(f"[PROMPT_CACHE] Error recording stats: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregate cache statistics.

        Returns:
            Dictionary with comprehensive cache performance metrics including:
            - total_requests: Total number of tracked requests
            - total_prompt_tokens: Total prompt tokens across all requests
            - total_cached_tokens: Total tokens served from cache
            - overall_cache_hit_rate_pct: Percentage of prompt tokens cached
            - request_cache_hit_rate_pct: Percentage of requests with cache hits
            - estimated_input_cost_savings_pct: Estimated cost reduction
            - recent_requests: Last 20 request summaries
        """
        with self._lock:
            total_reqs = self._total_requests
            total_prompt = self._total_prompt_tokens
            total_cached = self._total_cached_tokens
            total_completion = self._total_completion_tokens
            hits = sum(1 for s in self._history if s.cache_hit)
            recent = self._history[-20:] if self._history else []

        overall_hit_rate = (
            (total_cached / total_prompt * 100) if total_prompt > 0 else 0.0
        )
        overall_savings = (
            (total_cached * 50.0 / total_prompt) if total_prompt > 0 else 0.0
        )
        request_hit_rate = (hits / total_reqs * 100) if total_reqs > 0 else 0.0

        return {
            "total_requests": total_reqs,
            "total_prompt_tokens": total_prompt,
            "total_cached_tokens": total_cached,
            "total_completion_tokens": total_completion,
            "overall_cache_hit_rate_pct": round(overall_hit_rate, 2),
            "request_cache_hit_rate_pct": round(request_hit_rate, 2),
            "estimated_input_cost_savings_pct": round(overall_savings, 2),
            "recent_requests": [
                {
                    "model": s.model,
                    "cached_tokens": s.cached_tokens,
                    "total_prompt_tokens": s.total_prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "hit_rate_pct": round(s.cache_hit_rate, 1),
                    "savings_pct": round(s.estimated_savings_pct, 1),
                }
                for s in recent
            ],
        }

    def get_summary(self) -> str:
        """
        Get a human-readable summary of cache performance.

        Returns:
            Formatted string summary
        """
        stats = self.get_stats()
        return (
            f"Prompt Cache Summary:\n"
            f"  Requests: {stats['total_requests']}\n"
            f"  Prompt Tokens: {stats['total_prompt_tokens']:,}\n"
            f"  Cached Tokens: {stats['total_cached_tokens']:,}\n"
            f"  Cache Hit Rate: {stats['overall_cache_hit_rate_pct']}%\n"
            f"  Request Hit Rate: {stats['request_cache_hit_rate_pct']}%\n"
            f"  Est. Cost Savings: {stats['estimated_input_cost_savings_pct']}%"
        )

    def reset(self):
        """Reset all statistics."""
        with self._lock:
            self._history.clear()
            self._total_requests = 0
            self._total_prompt_tokens = 0
            self._total_cached_tokens = 0
            self._total_completion_tokens = 0
        logger.info("[PROMPT_CACHE] Statistics reset")


# =============================================================================
# GLOBAL MONITOR INSTANCE
# =============================================================================

cache_monitor = PromptCacheMonitor()
"""Global prompt cache monitor instance. Use this across the application."""
