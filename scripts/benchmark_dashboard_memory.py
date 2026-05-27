#!/usr/bin/env python3
"""Benchmark dashboard reader memory usage with 50K+ synthetic entries.

Generates a realistic synthetic usage.jsonl, runs compute_stats(hours=24),
and reports peak memory measured via tracemalloc.

Usage:
    uv run python scripts/benchmark_dashboard_memory.py [entry_count]

    Default entry_count is 50000.
"""

import json
import random
import sys
import tempfile
import time
import tracemalloc
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path so we can import the dashboard reader.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ruff: noqa: E402
from src.seven_bridges.dashboard.reader import compute_stats

# ---------------------------------------------------------------------------
# Synthetic data generation parameters
# ---------------------------------------------------------------------------

BACKENDS = ["kimi", "deepseek", "ollama", "openai", "siliconflow"]
MODELS: dict[str, list[str]] = {
    "kimi": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-opus-4-6",
        "claude-sonnet-4-6",
    ],
    "deepseek": [
        "claude-sonnet-4-5",
        "claude-sonnet-4-6",
        "claude-haiku-4-6",
    ],
    "ollama": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
        "claude-haiku-4-6",
    ],
    "openai": [
        "claude-sonnet-4-6",
        "claude-haiku-4-6",
    ],
    "siliconflow": [
        "siliconflow-minimax-m2.5",
        "siliconflow-deepseek-v3",
    ],
}

# Token profiles: (prompt range, completion range, cache-hit probability)
TOKEN_PROFILES = {
    "small": ((10, 200), (5, 100), 0.6),
    "medium": ((200, 2000), (100, 1000), 0.35),
    "large": ((2000, 20000), (1000, 8000), 0.1),
    "xlarge": ((20000, 80000), (4000, 16000), 0.02),
}

TOKEN_PROFILE_WEIGHTS = [0.55, 0.30, 0.12, 0.03]

STREAM_RATIO = 0.55
LATENCY_MIN_MS = 30
LATENCY_MAX_MS = 30000

# How many unique session IDs to generate
SESSIONS_PER_1K = 15


def generate_synthetic_entries(count: int, window_hours: int = 48) -> list[dict[str, object]]:
    """Build a list of realistic usage-log dicts distributed across *window_hours*."""

    now = datetime.now(UTC)

    num_sessions = max(50, count // 1000 * SESSIONS_PER_1K)
    sessions = [str(uuid.uuid4())[:8] for _ in range(num_sessions)]

    # Pre-select profiles so we can random.sample a flat list efficiently
    profile_names: list[str] = []
    profile_weights: list[float] = []
    for name, (_pr, _cr, _cp) in TOKEN_PROFILES.items():
        profile_names.append(name)
        profile_weights.append(TOKEN_PROFILE_WEIGHTS[list(TOKEN_PROFILES).index(name)])

    entries: list[dict[str, object]] = []

    backend_model_cache: dict[str, list[str]] = {}
    for backend in BACKENDS:
        backend_model_cache[backend] = [f"{backend}-m{n}" for n in range(1, 6)]

    for _ in range(count):
        backend = random.choice(BACKENDS)
        model = random.choice(MODELS[backend])
        backend_model = random.choice(backend_model_cache[backend])
        session = random.choice(sessions)

        # Distribute across the window with some clustering
        offset_seconds = int(random.expovariate(1 / (window_hours * 720)))
        offset_seconds = min(offset_seconds, window_hours * 3600 - 1)
        ts = (now - timedelta(seconds=offset_seconds)).isoformat()

        profile = random.choices(profile_names, weights=profile_weights, k=1)[0]
        (pt_min, pt_max), (ct_min, ct_max), cache_prob = TOKEN_PROFILES[profile]

        prompt_tokens = random.randint(pt_min, pt_max)
        completion_tokens = random.randint(ct_min, ct_max)

        cache_hit_tokens = 0
        if random.random() < cache_prob:
            cache_hit_tokens = random.randint(0, max(1, prompt_tokens // 3))

        is_stream = random.random() < STREAM_RATIO
        latency = random.randint(LATENCY_MIN_MS, LATENCY_MAX_MS)

        cost = round(
            (prompt_tokens * 0.40 + completion_tokens * 4.00 + cache_hit_tokens * 0.15) / 1_000_000,
            6,
        )

        entry: dict[str, object] = {
            "timestamp": ts,
            "session_id": session,
            "client_app": None,
            "user_agent": "testclient",
            "api_key_prefix": "ollama",
            "bridge": backend,
            "model_alias": model,
            "backend_model": backend_model,
            "response_id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "stream": is_stream,
            "max_tokens": random.choice([100, 1000, 4096, 8192, 16384]),
            "thinking_enabled": random.random() < 0.25,
            "thinking_budget": None,
            "tool_count": random.choices(
                [0, 1, 2, 3, 4, 5, 8], weights=[0.35, 0.25, 0.15, 0.1, 0.07, 0.05, 0.03]
            )[0],
            "tool_names": [],
            "message_count": random.choices(
                [1, 2, 3, 5, 8, 15, 30], weights=[0.2, 0.25, 0.2, 0.15, 0.1, 0.07, 0.03]
            )[0],
            "has_images": random.random() < 0.08,
            "has_video": False,
            "temperature": None if random.random() < 0.4 else round(random.random(), 2),
            "top_p": None,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cached_tokens": cache_hit_tokens,
                "prompt_cache_hit_tokens": cache_hit_tokens if cache_hit_tokens > 0 else None,
                "prompt_cache_miss_tokens": None,
            },
            "stop_reason": "end_turn",
            "estimated_cost_usd": cost,
            "latency_ms": latency,
            "client_metadata": None,
        }
        entries.append(entry)

    # Sort by timestamp so the log is ordered (matters for "recent entries")
    entries.sort(key=lambda e: str(e.get("timestamp", "")))
    return entries


def write_jsonl(path: Path, entries: list[dict[str, object]]) -> int:
    """Write entries as JSONL and return file size in bytes."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            json.dump(entry, f, separators=(",", ":"))
            f.write("\n")
    return path.stat().st_size


def measure_peak_memory(
    func, *args: object, **kwargs: object
) -> tuple[object, float, float, float]:
    """Run *func* and return (result, elapsed_s, current_mb, peak_mb)."""
    tracemalloc.clear_traces()
    tracemalloc.start()

    t0 = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - t0

    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return result, elapsed, current_bytes / (1024 * 1024), peak_bytes / (1024 * 1024)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    entry_count = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
    window_hours = 48  # generate entries across 48h, but query 24h

    print("=" * 64)
    print(f"Dashboard Memory Benchmark: {entry_count:,} entries")
    print("=" * 64)
    print()

    # ---- 1. Generate synthetic data ---------------------------------------
    print(f"[1/4] Generating {entry_count:,} synthetic entries (spread across {window_hours}h)...")
    t0 = time.perf_counter()
    entries = generate_synthetic_entries(entry_count, window_hours)
    gen_elapsed = time.perf_counter() - t0
    print(f"      Generated {len(entries):,} entries in {gen_elapsed:.1f}s")

    # Estimate in-memory size of the entries list (rough)
    sample = json.dumps(entries[0], separators=(",", ":"))
    est_mb = len(sample.encode()) * len(entries) / (1024 * 1024)
    print(f"      Estimated JSONL file size: {est_mb:.1f} MB")

    # ---- 2. Write to temp file --------------------------------------------
    print()
    print("[2/4] Writing entries to temporary JSONL file...")
    t0 = time.perf_counter()
    tmp_path = Path(tempfile.mktemp(suffix=".jsonl"))
    actual_bytes = write_jsonl(tmp_path, entries)
    write_elapsed = time.perf_counter() - t0
    actual_mb = actual_bytes / (1024 * 1024)
    print(f"      Wrote {actual_mb:.1f} MB in {write_elapsed:.1f}s")
    print(f"      Temp file: {tmp_path}")

    # Free the entries list before measuring compute_stats memory.
    del entries

    # ---- 3. Run compute_stats and measure memory --------------------------
    print()
    print("[3/4] Running compute_stats(hours=24) with tracemalloc...")
    result, elapsed, current_mb, peak_mb = measure_peak_memory(
        compute_stats, usage_path=str(tmp_path), hours=24
    )

    print(f"      Wall-clock time: {elapsed:.2f}s")
    print(f"      Current memory (after call): {current_mb:.1f} MB")
    print(f"      Peak memory:                {peak_mb:.1f} MB")

    # ---- 4. Validate output and report ------------------------------------
    print()
    print("[4/4] Validation and report")

    aggs = result.get("aggregates", {})
    total_requests = aggs.get("total_requests", 0)
    total_input = aggs.get("total_input_tokens", 0)
    total_output = aggs.get("total_output_tokens", 0)
    total_cost = aggs.get("total_cost", 0)
    n_backends = len(result.get("by_backend", []))
    n_models = len(result.get("by_model", []))
    n_sessions = len(result.get("by_session", []))
    n_buckets = len(result.get("time_series", {}).get("labels", []))
    n_recent = len(result.get("recent_requests", []))

    print(f"      Total requests in window:   {total_requests:,}")
    print(f"      Total input tokens:          {total_input:,}")
    print(f"      Total output tokens:         {total_output:,}")
    print(f"      Estimated cost:              ${total_cost:,.2f}")
    print(f"      Backend breakdowns:          {n_backends}")
    print(f"      Model breakdowns:            {n_models}")
    print(f"      Top sessions:                {n_sessions}")
    print(f"      Time-series buckets:         {n_buckets}")
    print(f"      Recent requests:             {n_recent}")

    # Sanity checks
    assert total_requests > 0, "Expected non-zero request count"
    assert n_backends > 0, "Expected at least one backend"
    assert n_models > 0, "Expected at least one model"
    assert n_buckets > 0, "Expected time-series buckets"
    assert n_recent <= 50, "Recent requests should be at most 50"

    print()
    print("-" * 64)
    limit_mb = 128.0
    if peak_mb < limit_mb:
        print(f"RESULT: PASS  (peak {peak_mb:.1f} MB < {limit_mb:.0f} MB limit)")
    else:
        print(f"RESULT: FAIL  (peak {peak_mb:.1f} MB >= {limit_mb:.0f} MB limit)")

    # Summary table
    print()
    print("Summary:")
    print(f"  Entry count:              {entry_count:>10,}")
    print(f"  File size:                {actual_mb:>10.1f} MB")
    print(f"  Wall-clock:               {elapsed:>10.2f}s")
    print(f"  Peak memory (tracemalloc): {peak_mb:>10.1f} MB")
    print(f"  Limit:                    {limit_mb:>10.0f} MB")
    print("-" * 64)

    # Cleanup
    tmp_path.unlink(missing_ok=True)

    return 0 if peak_mb < limit_mb else 1


if __name__ == "__main__":
    sys.exit(main())
