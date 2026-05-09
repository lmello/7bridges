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
    assert len(lines) == 2

    request_line = json.loads(lines[0])
    assert request_line["type"] == "request"
    assert request_line["method"] == "POST"
    assert request_line["path"] == "/v1/messages"
    assert request_line["body"]["model"] == "not-a-real-model"

    response_line = json.loads(lines[1])
    assert response_line["type"] == "response"
    assert response_line["status_code"] == 400
    assert "duration_ms" in response_line
