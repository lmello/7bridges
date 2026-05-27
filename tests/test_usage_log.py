"""Tests for usage logging module."""

import json

import seven_bridges.usage_log as usage_module
from seven_bridges.usage_log import _compute_cost, _log_usage, _rotate_if_needed


def test_log_usage_writes_jsonl_entry(monkeypatch, tmp_path):
    log_file = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", log_file)

    _log_usage(
        bridge_name="kimi",
        model_alias="claude-opus-4-6",
        backend_model="kimi-k2-6",
        response_id="chatcmpl-123",
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cached_tokens": 25,
            "prompt_cache_hit_tokens": None,
            "prompt_cache_miss_tokens": None,
        },
        stream=False,
        max_tokens=4096,
        thinking_enabled=True,
        thinking_budget=32000,
        tool_count=2,
        tool_names=["get_weather", "read_file"],
        message_count=3,
        has_images=False,
        has_video=False,
        temperature=0.7,
        top_p=None,
        session_id="sess-abc",
        client_app="cli",
        user_agent="claude-cli/2.1.150",
        api_key_prefix="sk-abc12",
        stop_reason="end_turn",
        client_metadata={"user_id": "u123"},
    )

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])

    assert entry["bridge"] == "kimi"
    assert entry["model_alias"] == "claude-opus-4-6"
    assert entry["backend_model"] == "kimi-k2-6"
    assert entry["response_id"] == "chatcmpl-123"
    assert entry["session_id"] == "sess-abc"
    assert entry["client_app"] == "cli"
    assert entry["user_agent"] == "claude-cli/2.1.150"
    assert entry["api_key_prefix"] == "sk-abc12"
    assert entry["stream"] is False
    assert entry["max_tokens"] == 4096
    assert entry["thinking_enabled"] is True
    assert entry["thinking_budget"] == 32000
    assert entry["tool_count"] == 2
    assert entry["tool_names"] == ["get_weather", "read_file"]
    assert entry["message_count"] == 3
    assert entry["has_images"] is False
    assert entry["has_video"] is False
    assert entry["temperature"] == 0.7
    assert entry["top_p"] is None
    assert entry["stop_reason"] == "end_turn"
    assert entry["client_metadata"] == {"user_id": "u123"}
    assert entry["usage"]["prompt_tokens"] == 100
    assert entry["usage"]["completion_tokens"] == 50
    assert entry["usage"]["total_tokens"] == 150
    assert entry["usage"]["cached_tokens"] == 25
    assert "timestamp" in entry


def test_log_usage_appends_multiple_lines(monkeypatch, tmp_path):
    log_file = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", log_file)

    for i in range(3):
        _log_usage(
            bridge_name="kimi",
            model_alias="claude-opus-4-6",
            backend_model="kimi-k2-6",
            response_id=f"chatcmpl-{i}",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            stream=False,
            max_tokens=100,
            thinking_enabled=None,
            thinking_budget=None,
            tool_count=0,
            tool_names=[],
            message_count=1,
            has_images=False,
            has_video=False,
            temperature=None,
            top_p=None,
            session_id=None,
            client_app=None,
            user_agent=None,
            api_key_prefix=None,
            stop_reason=None,
            client_metadata=None,
        )

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 3
    for i, line in enumerate(lines):
        entry = json.loads(line)
        assert entry["response_id"] == f"chatcmpl-{i}"


def test_log_usage_silently_ignores_write_errors(monkeypatch, tmp_path):
    log_file = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", log_file)

    # Make the directory read-only by pointing to a file path that can't be opened for append
    def bad_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", bad_open)

    # Should not raise
    _log_usage(
        bridge_name="kimi",
        model_alias="claude-opus-4-6",
        backend_model="kimi-k2-6",
        response_id="chatcmpl-err",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        stream=False,
        max_tokens=100,
        thinking_enabled=None,
        thinking_budget=None,
        tool_count=0,
        tool_names=[],
        message_count=1,
        has_images=False,
        has_video=False,
        temperature=None,
        top_p=None,
        session_id=None,
        client_app=None,
        user_agent=None,
        api_key_prefix=None,
        stop_reason=None,
        client_metadata=None,
    )


def test_log_usage_creates_parent_directory(monkeypatch, tmp_path):
    nested = tmp_path / "deep" / "nested" / "usage.jsonl"
    monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", nested)

    _log_usage(
        bridge_name="kimi",
        model_alias="claude-opus-4-6",
        backend_model="kimi-k2-6",
        response_id="chatcmpl-456",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        stream=False,
        max_tokens=100,
        thinking_enabled=None,
        thinking_budget=None,
        tool_count=0,
        tool_names=[],
        message_count=1,
        has_images=False,
        has_video=False,
        temperature=None,
        top_p=None,
        session_id=None,
        client_app=None,
        user_agent=None,
        api_key_prefix=None,
        stop_reason=None,
        client_metadata=None,
    )

    assert nested.exists()
    lines = nested.read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["response_id"] == "chatcmpl-456"


class TestRotateIfNeeded:
    """Tests for _rotate_if_needed() log rotation."""

    def test_no_rotation_when_file_missing(self, tmp_path):
        path = tmp_path / "nonexistent.jsonl"
        _rotate_if_needed(path, max_bytes=1024, keep_count=3)
        assert not path.exists()

    def test_no_rotation_when_under_threshold(self, tmp_path):
        path = tmp_path / "small.jsonl"
        path.write_text("short line\n")
        original_content = path.read_text()
        _rotate_if_needed(path, max_bytes=1024 * 1024, keep_count=3)
        assert path.exists()
        assert path.read_text() == original_content

    def test_rotation_shifts_files_when_over_threshold(self, tmp_path):
        path = tmp_path / "test.jsonl"
        # Write enough data to exceed a tiny threshold
        path.write_text("x" * 500)

        _rotate_if_needed(path, max_bytes=100, keep_count=3)

        # Original file should have been renamed to .1
        assert not path.exists()
        rotated = tmp_path / "test.1.jsonl"
        assert rotated.exists()
        assert rotated.read_text() == "x" * 500

    def test_rotation_shifts_existing_rotated_files(self, tmp_path):
        path = tmp_path / "test.jsonl"

        # Create pre-existing rotated files
        (tmp_path / "test.1.jsonl").write_text("old1")
        (tmp_path / "test.2.jsonl").write_text("old2")

        # Current log
        path.write_text("current" * 200)  # large enough

        _rotate_if_needed(path, max_bytes=100, keep_count=3)

        # After rotation:
        # test.3.jsonl should now contain old2
        # test.2.jsonl should now contain old1
        # test.1.jsonl should now contain the old current content
        # test.jsonl should not exist

        assert not path.exists()
        assert (tmp_path / "test.1.jsonl").read_text() == "current" * 200
        assert (tmp_path / "test.2.jsonl").read_text() == "old1"
        assert (tmp_path / "test.3.jsonl").read_text() == "old2"

    def test_rotation_prunes_oldest_within_managed_range(self, tmp_path):
        path = tmp_path / "test.jsonl"

        # Create pre-existing rotated files up to keep_count
        (tmp_path / "test.1.jsonl").write_text("a")
        (tmp_path / "test.2.jsonl").write_text("b")

        path.write_text("current" * 200)

        _rotate_if_needed(path, max_bytes=100, keep_count=2)

        # Old .2 is deleted, .1 shifts to .2, current becomes .1
        assert (tmp_path / "test.1.jsonl").read_text() == "current" * 200
        assert (tmp_path / "test.2.jsonl").read_text() == "a"

    def test_rotation_leaves_files_beyond_keep_count_untouched(self, tmp_path):
        path = tmp_path / "test.jsonl"

        # Create pre-existing rotated files -- .3 is beyond keep_count
        (tmp_path / "test.1.jsonl").write_text("a")
        (tmp_path / "test.3.jsonl").write_text("orphan")

        path.write_text("current" * 200)

        _rotate_if_needed(path, max_bytes=100, keep_count=2)

        # Files beyond keep_count are not managed by this rotation
        assert (tmp_path / "test.3.jsonl").exists()
        assert (tmp_path / "test.3.jsonl").read_text() == "orphan"

    def test_rotation_handles_os_errors_gracefully(self, tmp_path, monkeypatch):
        path = tmp_path / "test.jsonl"
        path.write_text("x" * 500)

        # Make Path.stat raise OSError
        def failing_stat(self, *, follow_symlinks=True):
            raise OSError("permission denied")

        monkeypatch.setattr(type(path), "stat", failing_stat)

        # Should not raise
        _rotate_if_needed(path, max_bytes=100, keep_count=3)

    def test_rotation_keep_count_zero_is_noop(self, tmp_path):
        path = tmp_path / "test.jsonl"
        path.write_text("x" * 500)

        _rotate_if_needed(path, max_bytes=100, keep_count=0)

        # File should remain untouched
        assert path.exists()
        assert path.read_text() == "x" * 500

    def test_log_usage_triggers_rotation_when_over_threshold(self, monkeypatch, tmp_path):
        log_file = tmp_path / "usage.jsonl"
        monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", log_file)

        # Lower the rotation threshold for the test
        monkeypatch.setattr(usage_module, "_MAX_LOG_BYTES", 100)
        monkeypatch.setattr(usage_module, "_MAX_ROTATED_LOG_FILES", 2)

        # Write a large first entry to exceed threshold
        _log_usage(
            bridge_name="kimi",
            model_alias="claude-opus-4-6",
            backend_model="kimi-k2-6",
            response_id="chatcmpl-1",
            usage={"prompt_tokens": 10000, "completion_tokens": 5000, "total_tokens": 15000},
            stream=False,
            max_tokens=100,
            thinking_enabled=None,
            thinking_budget=None,
            tool_count=0,
            tool_names=[],
            message_count=1,
            has_images=False,
            has_video=False,
            temperature=None,
            top_p=None,
            session_id=None,
            client_app=None,
            user_agent=None,
            api_key_prefix=None,
            stop_reason=None,
            client_metadata=None,
        )

        # First write: file is under threshold initially, so no rotation yet
        assert log_file.exists()

        # Write a second entry - file is now over threshold after writing first,
        # so rotation should happen before this write
        _log_usage(
            bridge_name="kimi",
            model_alias="claude-opus-4-6",
            backend_model="kimi-k2-6",
            response_id="chatcmpl-2",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            stream=False,
            max_tokens=100,
            thinking_enabled=None,
            thinking_budget=None,
            tool_count=0,
            tool_names=[],
            message_count=1,
            has_images=False,
            has_video=False,
            temperature=None,
            top_p=None,
            session_id=None,
            client_app=None,
            user_agent=None,
            api_key_prefix=None,
            stop_reason=None,
            client_metadata=None,
        )

        # The rotated file should exist with the first entry
        rotated = tmp_path / "usage.1.jsonl"
        assert rotated.exists()
        # The current log should have only the second entry
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["response_id"] == "chatcmpl-2"

        # The rotated file should have the first entry
        rotated_lines = rotated.read_text().strip().split("\n")
        assert len(rotated_lines) == 1
        rotated_entry = json.loads(rotated_lines[0])
        assert rotated_entry["response_id"] == "chatcmpl-1"


class TestComputeCost:
    """Tests for _compute_cost() with per-model pricing."""

    def test_default_pricing_no_backend(self) -> None:
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        cost = _compute_cost(usage)
        # Default: $0.40 + $4.00 = $4.40
        assert cost == 4.40

    def test_default_pricing_unknown_backend(self) -> None:
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        cost = _compute_cost(usage, backend="nonexistent")
        assert cost == 4.40

    def test_deepseek_pricing(self) -> None:
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        cost = _compute_cost(usage, backend="deepseek")
        # DeepSeek: $0.14 + $1.10 = $1.24
        assert cost == 1.24

    def test_deepseek_pricing_with_cache(self) -> None:
        usage = {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
            "prompt_cache_hit_tokens": 1_000_000,
        }
        cost = _compute_cost(usage, backend="deepseek")
        # DeepSeek: $0.14 + $1.10 + $0.014 = $1.254
        assert cost == 1.254

    def test_ollama_pricing_is_zero(self) -> None:
        usage = {"prompt_tokens": 10_000_000, "completion_tokens": 10_000_000}
        cost = _compute_cost(usage, backend="ollama")
        assert cost == 0.0

    def test_backward_compatible_no_new_params(self) -> None:
        """Callers that pass no backend/model still work."""
        usage = {"prompt_tokens": 100_000, "completion_tokens": 50_000}
        cost = _compute_cost(usage)
        # Default: (100K * 0.40 + 50K * 4.00) / 1M = $0.04 + $0.20 = $0.24
        assert cost == 0.24

    def test_cache_read_tokens_from_various_keys(self) -> None:
        """Cache read tokens are sourced from multiple upstream key names."""
        # prompt_cache_hit_tokens
        usage = {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
            "prompt_cache_hit_tokens": 1_000_000,
        }
        cost = _compute_cost(usage)
        # Default: $0.40 + $0.15 = $0.55
        assert cost == 0.55

        # cached-prompt-tokens (fireworks)
        usage2 = {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
            "cached-prompt-tokens": 1_000_000,
        }
        cost2 = _compute_cost(usage2)
        assert cost2 == 0.55

        # cached_tokens
        usage3 = {"prompt_tokens": 1_000_000, "completion_tokens": 0, "cached_tokens": 1_000_000}
        cost3 = _compute_cost(usage3)
        assert cost3 == 0.55

    def test_model_alias_passed_but_unused_when_no_specific_entry(self) -> None:
        """When model has no specific pricing, falls back to backend wildcard."""
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        cost = _compute_cost(usage, backend="deepseek", model_alias="claude-sonnet-4-6")
        # claude-sonnet-4-6 not explicitly in PRICING; falls back to deepseek wildcard
        assert cost == 1.24

    def test_zero_usage_returns_zero(self) -> None:
        usage: dict[str, int] = {}
        cost = _compute_cost(usage)
        assert cost == 0.0

    def test_model_specific_pricing_overrides_backend_wildcard(self, monkeypatch) -> None:
        """When a model has its own pricing entry, it takes precedence."""
        from seven_bridges.config import PRICING

        # Add a model-specific entry under deepseek
        monkeypatch.setitem(
            PRICING["deepseek"],
            "claude-sonnet-4-6",
            {"input": 0.07, "output": 0.55, "cache_read": 0.007},
        )
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
        cost = _compute_cost(usage, backend="deepseek", model_alias="claude-sonnet-4-6")
        assert cost == 0.62  # 0.07 + 0.55
