"""Smoke tests — basic health checks."""

from fastapi.testclient import TestClient

from seven_bridges.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_models():
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 3


def test_list_models_alias():
    resp = client.get("/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


def test_head_root():
    resp = client.head("/")
    assert resp.status_code == 200


def test_messages_requires_auth():
    resp = client.post(
        "/v1/messages",
        headers={"Content-Type": "application/json"},
        json={"model": "claude-opus-4-6", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert resp.status_code == 401


def test_messages_rejects_unknown_model():
    resp = client.post(
        "/v1/messages",
        headers={"x-api-key": "ollama", "Content-Type": "application/json"},
        json={
            "model": "not-a-real-model",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request_error"


def test_messages_rejects_missing_max_tokens():
    """max_tokens has a default of 4096, so this should work."""
    resp = client.post(
        "/v1/messages",
        headers={"x-api-key": "ollama", "Content-Type": "application/json"},
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    # Should not 422 since max_tokens has a default
    assert resp.status_code != 422
