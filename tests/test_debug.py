"""Tests for debug middleware."""

import json

import pytest
from fastapi.testclient import TestClient

import seven_bridges.debug as debug_module
from seven_bridges.main import app


@pytest.fixture
def debug_client(monkeypatch, tmp_path):
    """Create a client with debug enabled in a temp directory."""
    monkeypatch.setattr(debug_module, "DEBUG_ENABLED", True)
    monkeypatch.setattr(debug_module, "DEBUG_DIR", tmp_path)
    return TestClient(app)


def test_debug_middleware_captures_request_response(debug_client, tmp_path):
    resp = debug_client.post(
        "/v1/messages",
        headers={"x-api-key": "ollama", "Content-Type": "application/json"},
        json={
            "model": "not-a-real-model",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
        },
    )
    assert resp.status_code == 400

    # Check that a debug file was written
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    debug_file = files[0]
    assert debug_file.suffix == ".jsonl"

    lines = debug_file.read_text().strip().split("\n")
    # request + stream_body + response
    assert len(lines) == 3

    request_line = json.loads(lines[0])
    assert request_line["type"] == "request"
    assert request_line["method"] == "POST"
    assert request_line["path"] == "/v1/messages"
    assert request_line["body"]["model"] == "not-a-real-model"

    stream_body_line = json.loads(lines[1])
    assert stream_body_line["type"] == "stream_body"
    assert "text" in stream_body_line
    assert "content_length" in stream_body_line
    assert "handler_latency_ms" in stream_body_line
    assert "stream_duration_ms" in stream_body_line
    assert isinstance(stream_body_line["handler_latency_ms"], (int, float))
    assert isinstance(stream_body_line["stream_duration_ms"], (int, float))

    response_line = json.loads(lines[2])
    assert response_line["type"] == "response"
    assert response_line["status_code"] == 400
    assert "duration_ms" in response_line
    assert isinstance(response_line["duration_ms"], (int, float))
    # Streaming placeholder, not the actual text
    assert "streaming_response" in response_line["body"]


def test_debug_middleware_cleans_up_old_logs(monkeypatch, tmp_path):
    """Only the 100 most recent debug log files are kept."""
    monkeypatch.setattr(debug_module, "DEBUG_ENABLED", True)
    monkeypatch.setattr(debug_module, "DEBUG_DIR", tmp_path)

    # Create 105 old log files
    for i in range(105):
        f = tmp_path / f"old_{i:03d}.jsonl"
        f.write_text('{"type":"request"}\n')

    client = TestClient(app)
    client.head("/health")

    # Cleanup runs before the new log is created, so:
    # 105 old → prune to 100 → +1 new request = 101 total
    files = sorted(tmp_path.iterdir())
    assert len(files) == 101


def test_debug_middleware_handles_stream_error(monkeypatch, tmp_path):
    """If a streaming response raises mid-way, the middleware logs the error
    and returns a graceful 500 instead of crashing."""
    import asyncio

    async def broken_stream():
        yield b"event: message_start\ndata: {}\n\n"
        raise RuntimeError("boom")

    # Create a mock response that looks like what BaseHTTPMiddleware returns
    class MockWrappedResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {}
            self.media_type = "text/event-stream"
            self.body_iterator = broken_stream()

    monkeypatch.setattr(debug_module, "DEBUG_ENABLED", True)
    monkeypatch.setattr(debug_module, "DEBUG_DIR", tmp_path)

    mw = debug_module.DebugMiddleware(app)
    log_path = tmp_path / "test.jsonl"

    body_text, rebuilt = asyncio.run(
        mw._capture_streaming_response(
            MockWrappedResponse(), log_path, started_at=0.0, handler_done_at=0.0
        )
    )

    # Should report the error in the captured body text
    assert "stream_error" in body_text
    assert "boom" in body_text

    # Rebuilt response should be a 500
    assert rebuilt.status_code == 500

    # Log should contain the stream_error entry
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1
    error_line = json.loads(lines[0])
    assert error_line["type"] == "stream_error"
    assert "boom" in error_line["error"]
    assert "traceback" in error_line
