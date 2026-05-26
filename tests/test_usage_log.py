"""Tests for usage logging module."""

import json

import seven_bridges.usage_log as usage_module
from seven_bridges.usage_log import _log_usage


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
