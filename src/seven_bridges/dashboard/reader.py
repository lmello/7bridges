"""Reads and aggregates usage/error JSONL files for the dashboard.

Processes JSONL files in a single streaming pass so memory stays proportional to
the working-set size (accumulators + bounded recent-entry buffers), not the full
log-file size.
"""

import contextlib
import heapq
import json
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from seven_bridges.usage_log import _compute_cost as _compute_cost_from_usage

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_USAGE_PATH = PROJECT_ROOT / "logs" / "usage.jsonl"
DEFAULT_ERROR_PATH = PROJECT_ROOT / "logs" / "errors.jsonl"

# Maximum number of recent entries returned by the API.
_RECENT_LIMIT = 50


# Maximum rotated log files to scan (matches usage_log._MAX_ROTATED_LOG_FILES).
_MAX_ROTATED = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rotated_files(base_path: Path, max_rotation: int = _MAX_ROTATED) -> list[Path]:
    """Return *base_path* plus any existing rotated siblings, oldest first.

    Rotated files follow the naming convention ``stem.N.suffix`` (e.g.
    ``usage.1.jsonl``, ``usage.2.jsonl``).  The list is ordered with the
    oldest rotated file first and the current file last so that the
    ``_RecentTracker`` naturally keeps the newest entries.
    """
    files: list[Path] = []
    for i in range(max_rotation, 0, -1):
        rotated = base_path.with_suffix(f".{i}{base_path.suffix}")
        if rotated.exists():
            files.append(rotated)
    if base_path.exists():
        files.append(base_path)
    return files


def _bucket_hours_for_window(hours: int) -> int:
    """Return the bucket width in hours for the given time window.

    ===========  =====  ============
    Window       Width  Bucket count
    ===========  =====  ============
    <= 24 h      1 h    <= 24
    <= 168 h     2 h    <= 84
    > 168 h      12 h   <= 60
    ===========  =====  ============
    """
    if hours <= 24:
        return 1
    if hours <= 168:
        return 2
    return 12


def _bucket_label(ts: datetime, bucket_hours: int) -> str:
    """Return an ISO-8601 label for the bucket containing *ts*."""
    hour_block = (ts.hour // bucket_hours) * bucket_hours
    dt = ts.replace(hour=hour_block, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int = 0,
    backend: str | None = None,
    model_alias: str | None = None,
) -> float:
    """Compute estimated cost in USD.

    Delegates to ``usage_log._compute_cost`` to keep the pricing formula in one place.
    """
    usage: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_cache_hit_tokens": cache_hit_tokens,
    }
    return _compute_cost_from_usage(usage, backend=backend, model_alias=model_alias)


def _parse_jsonl_stream(path: Path) -> Iterator[dict[str, Any]]:
    """Yield parsed dicts from a JSONL file one at a time.

    Skips malformed lines silently.  Yields nothing when the file is missing
    or unreadable (the caller treats an empty stream as zero entries).
    """
    if not path.exists():
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into a list (kept for backward compatibility).

    Prefer ``_parse_jsonl_stream`` for memory-constrained paths; this function
    is now a convenience wrapper around the stream.
    """
    return list(_parse_jsonl_stream(path))


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


# ---------------------------------------------------------------------------
# Bounded recent-entry tracker
# ---------------------------------------------------------------------------


class _RecentTracker:
    """Track up to *max_size* entries with the most-recent timestamps.

    Uses a min-heap keyed by (timestamp, counter, entry) so only the
    *max_size* entries are retained in memory at any point.  Call
    :meth:`get_sorted` at the end to retrieve them newest-first.
    """

    def __init__(self, max_size: int = _RECENT_LIMIT) -> None:
        self._max_size = max_size
        self._heap: list[tuple[str, int, dict[str, Any]]] = []
        self._counter = 0

    def add(self, entry: dict[str, Any]) -> None:
        ts: str = entry.get("timestamp", "")
        heapq.heappush(self._heap, (ts, self._counter, entry))
        self._counter += 1
        if len(self._heap) > self._max_size:
            heapq.heappop(self._heap)

    def get_sorted(self) -> list[dict[str, Any]]:
        """Return entries sorted by timestamp descending (newest first)."""
        entries = [item[2] for item in self._heap]
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return entries


# ---------------------------------------------------------------------------
# Shared per-entry accumulator helpers
# ---------------------------------------------------------------------------


def _extract_usage(entry: dict[str, Any]) -> tuple[int, int, int]:
    """Return (prompt_tokens, completion_tokens, cache_hit_tokens) from an entry."""
    u: dict[str, Any] = entry.get("usage", {})
    pt = u.get("prompt_tokens", 0) or 0
    ct = u.get("completion_tokens", 0) or 0
    cached = (
        u.get("prompt_cache_hit_tokens")
        or u.get("cached-prompt-tokens")
        or u.get("cached_tokens")
        or 0
    )
    return pt, ct, cached


def _resolve_cost(entry: dict[str, Any], pt: int, ct: int, cached: int) -> float:
    """Return the cost for an entry, computing it on-the-fly when the log doesn't contain one."""
    cost = entry.get("estimated_cost_usd")
    if cost is None:
        cost = _compute_cost(
            pt,
            ct,
            cached,
            backend=entry.get("bridge"),
            model_alias=entry.get("model_alias"),
        )
    return float(cost)


# ---------------------------------------------------------------------------
# Main stats computer
# ---------------------------------------------------------------------------


def compute_stats(
    usage_path: str | None = None,
    error_path: str | None = None,
    hours: int = 24,
    backends: list[str] | None = None,
) -> dict[str, Any]:
    """Compute aggregated dashboard statistics from usage and error logs.

    Returns a dict with aggregates, breakdowns, time series, and recent entries.

    Processes JSONL files in a single streaming pass — memory is O(buckets +
    unique backends + unique models + unique sessions + _RECENT_LIMIT), **not**
    O(total entries).
    """
    u_path = Path(usage_path) if usage_path else DEFAULT_USAGE_PATH
    e_path = Path(error_path) if error_path else DEFAULT_ERROR_PATH

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=hours)
    bucket_hours = _bucket_hours_for_window(hours)
    backend_set = {b.lower() for b in backends} if backends else None

    # ---- Time-series buckets (pre-built) ----
    bucket_start = cutoff.replace(minute=0, second=0, microsecond=0)
    # Floor to the nearest bucket boundary (no-op when bucket_hours == 1).
    floor_hour = (bucket_start.hour // bucket_hours) * bucket_hours
    bucket_start = bucket_start.replace(hour=floor_hour)
    bucket_end = now.replace(minute=0, second=0, microsecond=0)
    buckets: dict[str, dict[str, Any]] = {}
    hour_dt = bucket_start
    while hour_dt <= bucket_end:
        label = hour_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        buckets[label] = {
            "requests": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "errors": 0,
            "tokens_cache_hit": 0,
            "tokens_cache_miss": 0,
        }
        hour_dt += timedelta(hours=bucket_hours)

    # ---- Accumulators (all updated in the single streaming pass) ----
    total_requests = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    latency_count = 0
    cache_hit_tokens_total = 0
    cache_miss_tokens_total = 0
    stream_count = 0

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

    session_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "last_active": "",
        }
    )

    recent_usage_tracker = _RecentTracker(_RECENT_LIMIT)

    # ---- Stream pass over all usage files (current + rotated) ----
    usage_files = _rotated_files(u_path) if hours > 24 else [u_path]
    for entry_file in usage_files:
        for entry in _parse_jsonl_stream(entry_file):
            ts = _parse_iso(entry.get("timestamp", ""))
            if ts is None or ts < cutoff:
                continue

            # Backend filter gate (usage)
            if backend_set is not None:
                bridge = (entry.get("bridge") or "unknown").lower()
                if bridge not in backend_set:
                    continue

            recent_usage_tracker.add(entry)
            total_requests += 1

            pt, ct, cached = _extract_usage(entry)
            total_input_tokens += pt
            total_output_tokens += ct
            cache_hit_tokens_total += cached
            # Per FR-1.3: cache-miss fallback chain
            usage_for_cache: dict[str, Any] = entry.get("usage", {})
            pcmt = usage_for_cache.get("prompt_cache_miss_tokens")
            if pcmt is not None and pcmt >= 0:
                cache_miss = max(0, pcmt)
            elif (
                usage_for_cache.get("prompt_cache_hit_tokens") is not None
                or usage_for_cache.get("cached-prompt-tokens") is not None
                or usage_for_cache.get("cached_tokens") is not None
            ):
                cache_miss = max(0, pt - cached)
            else:
                cache_miss = 0
            cache_miss_tokens_total += cache_miss

            # Cost
            cost = _resolve_cost(entry, pt, ct, cached)
            with contextlib.suppress(TypeError, ValueError):
                total_cost += cost

            # Latency
            lat = entry.get("latency_ms")
            if lat is not None:
                with contextlib.suppress(TypeError, ValueError):
                    total_latency += float(lat)
                    latency_count += 1

            # Stream
            if entry.get("stream"):
                stream_count += 1

            # --- Backend accumulation ---
            backend = entry.get("bridge", "unknown")
            bd = backend_data[backend]
            bd["requests"] += 1
            bd["input_tokens"] += pt
            bd["output_tokens"] += ct
            bd["cache_hit_tokens"] += cached
            bd["cache_miss_tokens"] += cache_miss
            with contextlib.suppress(TypeError, ValueError):
                bd["cost"] += cost
            if lat is not None:
                with contextlib.suppress(TypeError, ValueError):
                    bd["latency_ms_total"] += float(lat)
                    bd["latency_count"] += 1

            # --- Model accumulation ---
            model = entry.get("model_alias", "unknown")
            model_data[model]["requests"] += 1
            model_data[model]["input_tokens"] += pt
            model_data[model]["output_tokens"] += ct
            with contextlib.suppress(TypeError, ValueError):
                model_data[model]["cost"] += cost
            if lat is not None:
                with contextlib.suppress(TypeError, ValueError):
                    model_data[model]["latency_ms_total"] += float(lat)
                    model_data[model]["latency_count"] += 1
            if model not in model_backend:
                model_backend[model] = backend

            # --- Session accumulation ---
            sid = entry.get("session_id") or "unknown"
            session_data[sid]["requests"] += 1
            session_data[sid]["input_tokens"] += pt
            session_data[sid]["output_tokens"] += ct
            with contextlib.suppress(TypeError, ValueError):
                session_data[sid]["cost"] += cost
            ts_str = entry.get("timestamp", "")
            if ts_str > session_data[sid]["last_active"]:
                session_data[sid]["last_active"] = ts_str

            # --- Time-series bucket ---
            bucket_key = _bucket_label(ts, bucket_hours)
            if bucket_key in buckets:
                buckets[bucket_key]["requests"] += 1
                buckets[bucket_key]["tokens_in"] += pt
                buckets[bucket_key]["tokens_out"] += ct
                with contextlib.suppress(TypeError, ValueError):
                    buckets[bucket_key]["cost"] += cost
                buckets[bucket_key]["tokens_cache_hit"] += cached
                buckets[bucket_key]["tokens_cache_miss"] += cache_miss

    # ---- Error entries (streaming, all files) ----
    filtered_error_count = 0
    recent_error_tracker = _RecentTracker(_RECENT_LIMIT)

    error_files = _rotated_files(e_path) if hours > 24 else [e_path]
    for entry_file in error_files:
        for entry in _parse_jsonl_stream(entry_file):
            ts = _parse_iso(entry.get("timestamp", ""))
            if ts is None or ts < cutoff:
                continue

            # Backend filter gate (errors)
            if backend_set is not None:
                bridge = (entry.get("bridge") or "unknown").lower()
                if bridge not in backend_set:
                    continue

            filtered_error_count += 1
            recent_error_tracker.add(entry)

            backend = entry.get("bridge", "unknown")
            backend_data[backend]["errors"] += 1

            bucket_key = _bucket_label(ts, bucket_hours)
            if bucket_key in buckets:
                buckets[bucket_key]["errors"] += 1

    # ---- Derived aggregates ----
    avg_latency_ms = (total_latency / latency_count) if latency_count > 0 else 0.0
    cache_hit_rate = 0.0
    if (cache_hit_tokens_total + cache_miss_tokens_total) > 0:
        cache_hit_rate = round(
            cache_hit_tokens_total / (cache_hit_tokens_total + cache_miss_tokens_total) * 100,
            1,
        )
    error_rate = 0.0
    if (total_requests + filtered_error_count) > 0:
        error_rate = round(filtered_error_count / (total_requests + filtered_error_count) * 100, 1)
    stream_pct = round(stream_count / total_requests * 100, 1) if total_requests > 0 else 0.0

    # ---- Build output structures ----

    # By backend
    by_backend: list[dict[str, Any]] = []
    for backend_name, bd in sorted(backend_data.items()):
        total_reqs = bd["requests"] + bd["errors"]
        by_backend.append(
            {
                "backend": backend_name,
                "requests": bd["requests"],
                "input_tokens": bd["input_tokens"],
                "output_tokens": bd["output_tokens"],
                "cost": round(bd["cost"], 6),
                "avg_latency_ms": (
                    round(bd["latency_ms_total"] / bd["latency_count"], 1)
                    if bd["latency_count"] > 0
                    else 0.0
                ),
                "errors": bd["errors"],
                "error_rate": (
                    round(bd["errors"] / total_reqs * 100, 1) if total_reqs > 0 else 0.0
                ),
                "cache_hit_rate": (
                    round(
                        bd["cache_hit_tokens"]
                        / (bd["cache_hit_tokens"] + bd["cache_miss_tokens"])
                        * 100,
                        1,
                    )
                    if (bd["cache_hit_tokens"] + bd["cache_miss_tokens"]) > 0
                    else 0.0
                ),
            }
        )

    # By model
    by_model: list[dict[str, Any]] = []
    for model_name, md in sorted(model_data.items()):
        by_model.append(
            {
                "model_alias": model_name,
                "backend": model_backend.get(model_name, "unknown"),
                "requests": md["requests"],
                "input_tokens": md["input_tokens"],
                "output_tokens": md["output_tokens"],
                "cost": round(md["cost"], 6),
                "avg_latency_ms": (
                    round(md["latency_ms_total"] / md["latency_count"], 1)
                    if md["latency_count"] > 0
                    else 0.0
                ),
            }
        )

    # By session (top 20 by request count)
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

    # Time series
    sorted_labels = sorted(buckets.keys())
    backend_label = ",".join(backends) if backends else "all"
    time_series: dict[str, Any] = {
        "labels": sorted_labels,
        "requests": [buckets[label]["requests"] for label in sorted_labels],
        "tokens_in": [buckets[label]["tokens_in"] for label in sorted_labels],
        "tokens_out": [buckets[label]["tokens_out"] for label in sorted_labels],
        "tokens_cache_hit": [buckets[label]["tokens_cache_hit"] for label in sorted_labels],
        "tokens_cache_miss": [buckets[label]["tokens_cache_miss"] for label in sorted_labels],
        "cost": [round(buckets[label]["cost"], 6) for label in sorted_labels],
        "errors": [buckets[label]["errors"] for label in sorted_labels],
        "backend": [backend_label for _ in sorted_labels],
    }

    # Recent entries
    recent_requests = recent_usage_tracker.get_sorted()
    recent_errors = recent_error_tracker.get_sorted()

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
        "total_errors_24h": filtered_error_count,
    }
