"""Reads and aggregates usage/error JSONL files for the dashboard."""

import contextlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_USAGE_PATH = PROJECT_ROOT / "logs" / "usage.jsonl"
DEFAULT_ERROR_PATH = PROJECT_ROOT / "logs" / "errors.jsonl"


def _compute_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int = 0,
) -> float:
    """Compute estimated cost in USD.

    Pricing (per 1M tokens):
      - input tokens: $0.40
      - output tokens: $4.00
      - cache read tokens: $0.15
    """
    cost = (prompt_tokens * 0.40 + completion_tokens * 4.00 + cache_hit_tokens * 0.15) / 1_000_000
    return round(cost, 6)


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file, skipping malformed lines. Returns empty list if file is missing."""
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return entries


def _parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp to a UTC datetime. Returns None on failure."""
    try:
        # Handle timezone offsets and 'Z' suffix
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _format_number(n: int | float) -> str:
    """Format large numbers with compact suffixes."""
    if isinstance(n, float):
        if n < 10:
            return f"${n:.2f}"
        if n < 1000:
            return f"${n:.1f}"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n)) if isinstance(n, int) else f"{n:.1f}"


def compute_stats(
    usage_path: str | None = None,
    error_path: str | None = None,
    hours: int = 24,
) -> dict[str, Any]:
    """Compute aggregated dashboard statistics from usage and error logs.

    Returns a dict with aggregates, breakdowns, time series, and recent entries.
    """
    u_path = Path(usage_path) if usage_path else DEFAULT_USAGE_PATH
    e_path = Path(error_path) if error_path else DEFAULT_ERROR_PATH

    usage_entries = _parse_jsonl(u_path)
    error_entries = _parse_jsonl(e_path)

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=hours)

    # Filter usage entries by time window
    filtered_usage: list[dict[str, Any]] = []
    for entry in usage_entries:
        ts = _parse_iso(entry.get("timestamp", ""))
        if ts is not None and ts >= cutoff:
            filtered_usage.append(entry)

    # Filter error entries by time window
    filtered_errors: list[dict[str, Any]] = []
    for entry in error_entries:
        ts = _parse_iso(entry.get("timestamp", ""))
        if ts is not None and ts >= cutoff:
            filtered_errors.append(entry)

    # --- Aggregates ---
    total_requests = len(filtered_usage)
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    latency_count = 0
    cache_hit_tokens_total = 0
    cache_miss_tokens_total = 0
    stream_count = 0

    for entry in filtered_usage:
        u = entry.get("usage", {})
        prompt_tokens = u.get("prompt_tokens", 0) or 0
        completion_tokens = u.get("completion_tokens", 0) or 0
        cached_tokens = u.get("prompt_cache_hit_tokens") or u.get("cached_tokens") or 0
        total_input_tokens += prompt_tokens
        total_output_tokens += completion_tokens
        cache_hit_tokens_total += cached_tokens
        cache_miss_tokens_total += u.get("prompt_cache_miss_tokens") or 0

        cost = entry.get("estimated_cost_usd")
        if cost is None:
            cost = _compute_cost(prompt_tokens, completion_tokens, cached_tokens)
        with contextlib.suppress(TypeError, ValueError):
            total_cost += float(cost)

        lat = entry.get("latency_ms")
        if lat is not None:
            with contextlib.suppress(TypeError, ValueError):
                total_latency += float(lat)
                latency_count += 1

        if entry.get("stream"):
            stream_count += 1

    avg_latency_ms = (total_latency / latency_count) if latency_count > 0 else 0.0
    cache_hit_rate = 0.0
    if (cache_hit_tokens_total + cache_miss_tokens_total) > 0:
        cache_hit_rate = round(
            cache_hit_tokens_total / (cache_hit_tokens_total + cache_miss_tokens_total) * 100,
            1,
        )
    error_rate = 0.0
    if (total_requests + len(filtered_errors)) > 0:
        error_rate = round(len(filtered_errors) / (total_requests + len(filtered_errors)) * 100, 1)
    stream_pct = round(stream_count / total_requests * 100, 1) if total_requests > 0 else 0.0

    # --- By backend ---
    backend_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "latency_ms_total": 0.0,
            "latency_count": 0,
            "errors": 0,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
        }
    )
    for entry in filtered_usage:
        backend = entry.get("bridge", "unknown")
        bd = backend_data[backend]
        bd["requests"] += 1
        u = entry.get("usage", {})
        pt = u.get("prompt_tokens", 0) or 0
        ct = u.get("completion_tokens", 0) or 0
        cached = u.get("prompt_cache_hit_tokens") or u.get("cached_tokens") or 0
        bd["input_tokens"] += pt
        bd["output_tokens"] += ct
        bd["cache_hit_tokens"] += cached
        bd["cache_miss_tokens"] += u.get("prompt_cache_miss_tokens") or 0

        cost = entry.get("estimated_cost_usd")
        if cost is None:
            cost = _compute_cost(pt, ct, cached)
        with contextlib.suppress(TypeError, ValueError):
            bd["cost"] += float(cost)

        lat = entry.get("latency_ms")
        if lat is not None:
            with contextlib.suppress(TypeError, ValueError):
                bd["latency_ms_total"] += float(lat)
                bd["latency_count"] += 1

    for entry in filtered_errors:
        backend = entry.get("bridge", "unknown")
        backend_data[backend]["errors"] += 1

    by_backend: list[dict[str, Any]] = []
    for backend, bd in sorted(backend_data.items()):
        total_reqs = bd["requests"] + bd["errors"]
        by_backend.append(
            {
                "backend": backend,
                "requests": bd["requests"],
                "input_tokens": bd["input_tokens"],
                "output_tokens": bd["output_tokens"],
                "cost": round(bd["cost"], 6),
                "avg_latency_ms": round(bd["latency_ms_total"] / bd["latency_count"], 1)
                if bd["latency_count"] > 0
                else 0.0,
                "errors": bd["errors"],
                "error_rate": round(bd["errors"] / total_reqs * 100, 1) if total_reqs > 0 else 0.0,
                "cache_hit_rate": round(
                    bd["cache_hit_tokens"]
                    / (bd["cache_hit_tokens"] + bd["cache_miss_tokens"])
                    * 100,
                    1,
                )
                if (bd["cache_hit_tokens"] + bd["cache_miss_tokens"]) > 0
                else 0.0,
            }
        )

    # --- By model ---
    model_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "latency_ms_total": 0.0,
            "latency_count": 0,
        }
    )
    model_backend: dict[str, str] = {}
    for entry in filtered_usage:
        model = entry.get("model_alias", "unknown")
        model_data[model]["requests"] += 1
        u = entry.get("usage", {})
        pt = u.get("prompt_tokens", 0) or 0
        ct = u.get("completion_tokens", 0) or 0
        cached = u.get("prompt_cache_hit_tokens") or u.get("cached_tokens") or 0
        model_data[model]["input_tokens"] += pt
        model_data[model]["output_tokens"] += ct

        cost = entry.get("estimated_cost_usd")
        if cost is None:
            cost = _compute_cost(pt, ct, cached)
        with contextlib.suppress(TypeError, ValueError):
            model_data[model]["cost"] += float(cost)

        lat = entry.get("latency_ms")
        if lat is not None:
            with contextlib.suppress(TypeError, ValueError):
                model_data[model]["latency_ms_total"] += float(lat)
                model_data[model]["latency_count"] += 1

        if model not in model_backend:
            model_backend[model] = entry.get("bridge", "unknown")

    by_model: list[dict[str, Any]] = []
    for model, md in sorted(model_data.items()):
        by_model.append(
            {
                "model_alias": model,
                "backend": model_backend.get(model, "unknown"),
                "requests": md["requests"],
                "input_tokens": md["input_tokens"],
                "output_tokens": md["output_tokens"],
                "cost": round(md["cost"], 6),
                "avg_latency_ms": round(md["latency_ms_total"] / md["latency_count"], 1)
                if md["latency_count"] > 0
                else 0.0,
            }
        )

    # --- By session (top 20 by request count) ---
    session_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "last_active": "",
        }
    )
    for entry in filtered_usage:
        sid = entry.get("session_id") or "unknown"
        session_data[sid]["requests"] += 1
        u = entry.get("usage", {})
        pt = u.get("prompt_tokens", 0) or 0
        ct = u.get("completion_tokens", 0) or 0
        cached = u.get("prompt_cache_hit_tokens") or u.get("cached_tokens") or 0
        session_data[sid]["input_tokens"] += pt
        session_data[sid]["output_tokens"] += ct

        cost = entry.get("estimated_cost_usd")
        if cost is None:
            cost = _compute_cost(pt, ct, cached)
        with contextlib.suppress(TypeError, ValueError):
            session_data[sid]["cost"] += float(cost)

        # Track last active
        ts = entry.get("timestamp", "")
        if ts > session_data[sid]["last_active"]:
            session_data[sid]["last_active"] = ts

    top_sessions = sorted(session_data.items(), key=lambda x: x[1]["requests"], reverse=True)[:20]
    by_session: list[dict[str, Any]] = []
    for sid, sd in top_sessions:
        by_session.append(
            {
                "session_id": sid,
                "requests": sd["requests"],
                "input_tokens": sd["input_tokens"],
                "output_tokens": sd["output_tokens"],
                "cost": round(sd["cost"], 6),
                "last_active": sd["last_active"],
            }
        )

    # --- Time series (hourly buckets) ---
    # Build buckets spanning from cutoff to now, aligned to hour boundaries.
    # Floor cutoff to the previous full hour (inclusive), ceiling to the
    # current full hour (inclusive).  This guarantees every filtered entry
    # lands in a bucket regardless of timezone offset between server and UTC.
    bucket_start = cutoff.replace(minute=0, second=0, microsecond=0)
    bucket_end = now.replace(minute=0, second=0, microsecond=0)
    buckets: dict[str, dict[str, Any]] = {}
    hour_dt = bucket_start
    while hour_dt <= bucket_end:
        label = hour_dt.strftime("%Y-%m-%dT%H:00:00Z")
        buckets[label] = {"requests": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "errors": 0}
        hour_dt += timedelta(hours=1)

    for entry in filtered_usage:
        ts = _parse_iso(entry.get("timestamp", ""))
        if ts is None:
            continue
        hour_label = ts.strftime("%Y-%m-%dT%H:00:00Z")
        if hour_label in buckets:
            buckets[hour_label]["requests"] += 1
            u = entry.get("usage", {})
            pt = u.get("prompt_tokens", 0) or 0
            ct = u.get("completion_tokens", 0) or 0
            cached = u.get("prompt_cache_hit_tokens") or u.get("cached_tokens") or 0
            buckets[hour_label]["tokens_in"] += pt
            buckets[hour_label]["tokens_out"] += ct
            cost = entry.get("estimated_cost_usd")
            if cost is None:
                cost = _compute_cost(pt, ct, cached)
            with contextlib.suppress(TypeError, ValueError):
                buckets[hour_label]["cost"] += float(cost)

    for entry in filtered_errors:
        ts = _parse_iso(entry.get("timestamp", ""))
        if ts is None:
            continue
        hour_label = ts.strftime("%Y-%m-%dT%H:00:00Z")
        if hour_label in buckets:
            buckets[hour_label]["errors"] += 1

    # Sort labels chronologically
    sorted_labels = sorted(buckets.keys())
    time_series = {
        "labels": sorted_labels,
        "requests": [buckets[label]["requests"] for label in sorted_labels],
        "tokens_in": [buckets[label]["tokens_in"] for label in sorted_labels],
        "tokens_out": [buckets[label]["tokens_out"] for label in sorted_labels],
        "cost": [round(buckets[label]["cost"], 6) for label in sorted_labels],
        "errors": [buckets[label]["errors"] for label in sorted_labels],
    }

    # --- Recent entries (last 50) ---
    sorted_usage = sorted(filtered_usage, key=lambda x: x.get("timestamp", ""), reverse=True)
    sorted_errors = sorted(filtered_errors, key=lambda x: x.get("timestamp", ""), reverse=True)

    recent_requests = sorted_usage[:50]
    recent_errors = sorted_errors[:50]

    return {
        "aggregates": {
            "total_requests": total_requests,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost": round(total_cost, 6),
            "avg_latency_ms": round(avg_latency_ms, 1),
            "cache_hit_rate": cache_hit_rate,
            "error_rate": error_rate,
            "stream_pct": stream_pct,
        },
        "by_backend": by_backend,
        "by_model": by_model,
        "by_session": by_session,
        "time_series": time_series,
        "recent_requests": recent_requests,
        "recent_errors": recent_errors,
        "total_errors_24h": len(filtered_errors),
    }
