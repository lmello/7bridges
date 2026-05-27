"""Usage logging: persist per-request token counts to JSONL.

Every successful chat completion writes one line to logs/usage.jsonl
with the upstream usage payload plus request metadata for cost analysis.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

USAGE_LOG_PATH = Path(__file__).parent.parent.parent / "logs" / "usage.jsonl"


def _compute_cost(usage: dict[str, Any]) -> float:
    """Compute estimated cost in USD from usage statistics.

    Pricing (per 1M tokens):
      - input tokens: $0.40
      - output tokens: $4.00
      - cache read tokens: $0.15
    """
    input_tokens: int = usage.get("prompt_tokens", 0)
    output_tokens: int = usage.get("completion_tokens", 0)
    cache_read_tokens: int = usage.get("prompt_cache_hit_tokens") or usage.get("cached_tokens") or 0
    cost = (input_tokens * 0.40 + output_tokens * 4.00 + cache_read_tokens * 0.15) / 1_000_000
    return round(cost, 6)


def _compute_cache_hit_rate(usage: dict[str, Any]) -> float | None:
    """Compute cache hit rate as a percentage, or None if not applicable."""
    hit = usage.get("prompt_cache_hit_tokens")
    miss = usage.get("prompt_cache_miss_tokens")

    if isinstance(hit, int) and isinstance(miss, int) and (hit + miss) > 0:
        return round(hit / (hit + miss) * 100, 1)

    return None


def _log_usage(
    *,
    bridge_name: str,
    model_alias: str,
    backend_model: str,
    response_id: str | None,
    usage: dict[str, Any],
    stream: bool,
    max_tokens: int | None,
    thinking_enabled: bool | None,
    thinking_budget: str | None,
    tool_count: int,
    tool_names: list[str],
    message_count: int,
    has_images: bool,
    has_video: bool,
    temperature: float | None,
    top_p: float | None,
    session_id: str | None,
    client_app: str | None,
    user_agent: str | None,
    api_key_prefix: str | None,
    stop_reason: str | None,
    client_metadata: dict[str, Any] | None,
    estimated_cost_usd: float | None = None,
    latency_ms: float | None = None,
    cache_headers_sent: bool | None = None,
    cache_hit_rate: float | None = None,
) -> None:
    """Write a single usage event to logs/usage.jsonl.

    Failures are silently ignored so logging never breaks a request.
    """
    try:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "client_app": client_app,
            "user_agent": user_agent,
            "api_key_prefix": api_key_prefix,
            "bridge": bridge_name,
            "model_alias": model_alias,
            "backend_model": backend_model,
            "response_id": response_id,
            "stream": stream,
            "max_tokens": max_tokens,
            "thinking_enabled": thinking_enabled,
            "thinking_budget": thinking_budget,
            "tool_count": tool_count,
            "tool_names": tool_names,
            "message_count": message_count,
            "has_images": has_images,
            "has_video": has_video,
            "temperature": temperature,
            "top_p": top_p,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "cached_tokens": usage.get("cached_tokens"),
                "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
                "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
            },
            "estimated_cost_usd": estimated_cost_usd,
            "latency_ms": latency_ms,
            "cache_headers_sent": cache_headers_sent,
            "cache_hit_rate": cache_hit_rate,
            "stop_reason": stop_reason,
            "client_metadata": client_metadata,
        }
        USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
