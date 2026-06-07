"""End-to-end tests with mocked upstream APIs."""

import json

import respx
from fastapi.testclient import TestClient
from httpx import Response

import seven_bridges.usage_log as usage_module
from seven_bridges.config import settings
from seven_bridges.main import app

client = TestClient(app)

API_KEY = "ollama"


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": API_KEY, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# DeepSeek e2e tests
# ---------------------------------------------------------------------------


@respx.mock
def test_deepseek_non_streaming_text():
    route = respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-ds-1",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from DeepSeek!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "claude-sonnet-4-6"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "text"
    assert data["content"][0]["text"] == "Hello from DeepSeek!"
    assert data["stop_reason"] == "end_turn"
    assert data["usage"]["input_tokens"] == 10
    assert data["usage"]["output_tokens"] == 5

    # Verify the upstream request
    assert route.called
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["model"] == "deepseek-v4-pro"
    assert upstream["messages"][0]["role"] == "user"


@respx.mock
def test_deepseek_streaming_text():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-ds-2",
                "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-ds-2",
                "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
            }
        ),
    ]

    respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream"

    events = _parse_sse(resp.text)
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "claude-sonnet-4-6"

    # Find text deltas
    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 2
    assert text_deltas[0][1]["delta"]["text"] == "Hello"
    assert text_deltas[1][1]["delta"]["text"] == " world"

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"
    assert events[-1][0] == "message_stop"


@respx.mock
def test_deepseek_tool_call_non_streaming():
    respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-ds-3",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"location": "NYC"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "What's the weather in NYC?"}],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                }
            ],
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stop_reason"] == "tool_use"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "tool_use"
    assert data["content"][0]["name"] == "get_weather"
    assert data["content"][0]["input"] == {"location": "NYC"}


@respx.mock
@respx.mock
def test_deepseek_strips_images_when_fallback_disabled(monkeypatch):
    """Non-vision backends strip images and continue when fallback is disabled."""
    monkeypatch.setattr(settings, "vision_fallback_enabled", False)
    route = respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-ds-sr",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "I see text."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this:"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "abc123",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["content"][0]["text"] == "I see text."

    # Verify the image was stripped from the upstream request
    upstream_body = json.loads(route.calls.last.request.content)
    user_msg = upstream_body["messages"][0]
    assert user_msg["role"] == "user"
    assert "[image]" in str(user_msg["content"])


@respx.mock
def test_deepseek_upstream_error_mapping():
    respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            429,
            json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 429
    data = resp.json()
    assert data["type"] == "error"
    assert data["error"]["type"] == "rate_limit_error"


@respx.mock
def test_deepseek_thinking_passthrough():
    """Verify thinking/effort fields are sent to DeepSeek."""
    route = respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-ds-4",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Thoughtful."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Think hard"}],
            "max_tokens": 100,
            "thinking": {"type": "enabled"},
            "output_config": {"effort": "xhigh"},
            "stream": False,
        },
    )

    assert resp.status_code == 200
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["thinking"] == {"type": "enabled"}
    assert upstream["reasoning_effort"] == "xhigh"


@respx.mock
def test_deepseek_thinking_disabled():
    """Verify thinking=disabled is passed through to DeepSeek."""
    route = respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-ds-5",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Straight answer."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Quick answer"}],
            "max_tokens": 100,
            "thinking": {"type": "disabled"},
            "stream": False,
        },
    )

    assert resp.status_code == 200
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["thinking"] == {"type": "disabled"}


@respx.mock
def test_deepseek_thinking_adaptive():
    """Verify thinking=adaptive is mapped to enabled for DeepSeek."""
    route = respx.post("https://api.deepseek.com/beta/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-ds-6",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "deepseek-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Adaptive answer."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "Solve this"}],
            "max_tokens": 100,
            "thinking": {"type": "adaptive"},
            "stream": False,
        },
    )

    assert resp.status_code == 200
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["thinking"] == {"type": "enabled"}


# ---------------------------------------------------------------------------
# Kimi e2e tests
# ---------------------------------------------------------------------------


@respx.mock
def test_kimi_non_streaming_with_reasoning():
    respx.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-kimi-1",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "kimi-for-coding",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                            "reasoning_content": "Let me think...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "cached_tokens": 8,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "claude-opus-4-6"
    assert len(data["content"]) == 2
    assert data["content"][0]["type"] == "thinking"
    assert data["content"][0]["thinking"] == "Let me think..."
    assert data["content"][0]["signature"] == ""
    assert data["content"][1]["type"] == "text"
    assert data["content"][1]["text"] == "The answer is 42."
    assert data["usage"]["cache_read_input_tokens"] == 8


@respx.mock
def test_kimi_streaming_with_reasoning():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-kimi-2",
                "choices": [{"delta": {"reasoning_content": "Let me"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-kimi-2",
                "choices": [{"delta": {"reasoning_content": " think..."}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-kimi-2",
                "choices": [{"delta": {"content": "42"}, "finish_reason": "stop"}],
            }
        ),
    ]

    respx.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    # Find thinking deltas
    thinking_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "thinking_delta"
    ]
    assert len(thinking_deltas) == 2
    assert thinking_deltas[0][1]["delta"]["thinking"] == "Let me"
    assert thinking_deltas[1][1]["delta"]["thinking"] == " think..."

    # Find text delta
    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 1
    assert text_deltas[0][1]["delta"]["text"] == "42"

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"


@respx.mock
def test_kimi_accepts_images():
    respx.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-kimi-3",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "kimi-for-coding",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "It's a cat."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-opus-4-6",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is this?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "abc123",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"][0]["text"] == "It's a cat."

    # Verify upstream received image_url format
    upstream = json.loads(respx.routes[0].calls[0].request.content)
    user_msg = upstream["messages"][0]
    assert isinstance(user_msg["content"], list)
    assert user_msg["content"][1]["type"] == "image_url"
    assert "abc123" in user_msg["content"][1]["image_url"]["url"]


@respx.mock
def test_kimi_streaming_tool_calls():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-kimi-4",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "get_weather", "arguments": ""},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-kimi-4",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": '{"location": "'}}
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-kimi-4",
                "choices": [
                    {
                        "delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'NYC"}'}}]},
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        ),
    ]

    respx.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "Weather in NYC?"}],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                }
            ],
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    # Find tool_use start
    tool_starts = [
        e
        for e in events
        if e[0] == "content_block_start" and e[1]["content_block"]["type"] == "tool_use"
    ]
    assert len(tool_starts) == 1
    assert tool_starts[0][1]["content_block"]["name"] == "get_weather"

    # Find input_json_delta events
    json_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "input_json_delta"
    ]
    assert len(json_deltas) == 2
    assert json_deltas[0][1]["delta"]["partial_json"] == '{"location": "'
    assert json_deltas[1][1]["delta"]["partial_json"] == 'NYC"}'

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "tool_use"


@respx.mock
def test_kimi_non_streaming_logs_usage(monkeypatch, tmp_path):
    log_file = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", log_file)

    respx.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-kimi-usage-1",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "kimi-for-coding",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                    "cached_tokens": 5,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
            "x-claude-code-session-id": "sess-123",
            "User-Agent": "claude-cli/2.1.150",
        },
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
            "metadata": {"user_id": "u456"},
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                }
            ],
        },
    )

    assert resp.status_code == 200

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])

    assert entry["bridge"] == "kimi"
    assert entry["model_alias"] == "claude-opus-4-6"
    assert entry["backend_model"] == "kimi-for-coding"
    assert entry["response_id"] == "chatcmpl-kimi-usage-1"
    assert entry["session_id"] == "sess-123"
    assert entry["user_agent"] == "claude-cli/2.1.150"
    assert entry["api_key_prefix"] == "ollama"
    assert entry["stream"] is False
    assert entry["max_tokens"] == 100
    assert entry["tool_count"] == 1
    assert entry["tool_names"] == ["get_weather"]
    assert entry["message_count"] == 1
    assert entry["usage"]["prompt_tokens"] == 20
    assert entry["usage"]["completion_tokens"] == 10
    assert entry["usage"]["total_tokens"] == 30
    assert entry["usage"]["cached_tokens"] == 5
    assert entry["stop_reason"] == "end_turn"
    assert entry["client_metadata"] == {"user_id": "u456"}


@respx.mock
def test_kimi_streaming_logs_usage(monkeypatch, tmp_path):
    log_file = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage_module, "USAGE_LOG_PATH", log_file)

    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-kimi-usage-2",
                "choices": [{"delta": {"content": "Hi"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-kimi-usage-2",
                "choices": [{"delta": {"content": "!"}, "finish_reason": "stop"}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-kimi-usage-2",
                "choices": [],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 8,
                    "total_tokens": 23,
                    "cached_tokens": 3,
                },
            }
        ),
    ]

    respx.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 2

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])

    assert entry["bridge"] == "kimi"
    assert entry["response_id"] == "chatcmpl-kimi-usage-2"
    assert entry["stream"] is True
    assert entry["usage"]["prompt_tokens"] == 15
    assert entry["usage"]["completion_tokens"] == 8
    assert entry["usage"]["total_tokens"] == 23
    assert entry["usage"]["cached_tokens"] == 3


# ---------------------------------------------------------------------------
# Ollama e2e tests
# ---------------------------------------------------------------------------


@respx.mock
def test_ollama_non_streaming_text():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(
            200,
            json={
                "model": "qwen3.6:35b-a3b-coding-nvfp4",
                "created_at": "2024-01-01T00:00:00Z",
                "done": True,
                "done_reason": "stop",
                "message": {"role": "assistant", "content": "Hello from Ollama!"},
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-0",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "claude-sonnet-4-0"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "text"
    assert data["content"][0]["text"] == "Hello from Ollama!"
    assert data["stop_reason"] == "end_turn"
    assert data["usage"]["input_tokens"] == 10
    assert data["usage"]["output_tokens"] == 5

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == settings.ollama_sonnet_model


@respx.mock
def test_ollama_streaming_text():
    chunks = [
        {
            "model": "qwen3.6:35b-a3b-coding-nvfp4",
            "created_at": "2024-01-01T00:00:00Z",
            "done": False,
            "message": {"role": "assistant", "content": "Hello"},
        },
        {
            "model": "qwen3.6:35b-a3b-coding-nvfp4",
            "created_at": "2024-01-01T00:00:00Z",
            "done": False,
            "message": {"role": "assistant", "content": " world"},
        },
        {
            "model": "qwen3.6:35b-a3b-coding-nvfp4",
            "created_at": "2024-01-01T00:00:00Z",
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": ""},
            "prompt_eval_count": 10,
            "eval_count": 5,
        },
    ]

    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(
            200,
            text="\n".join(json.dumps(c) for c in chunks),
            headers={"Content-Type": "application/x-ndjson"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-0",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "claude-sonnet-4-0"

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 2
    assert text_deltas[0][1]["delta"]["text"] == "Hello"
    assert text_deltas[1][1]["delta"]["text"] == " world"

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"
    assert events[-1][0] == "message_stop"


@respx.mock
def test_ollama_tool_call_non_streaming():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(
            200,
            json={
                "model": "qwen3.6:35b-a3b-coding-nvfp4",
                "created_at": "2024-01-01T00:00:00Z",
                "done": True,
                "done_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": {"location": "NYC"},
                            }
                        }
                    ],
                },
                "prompt_eval_count": 20,
                "eval_count": 15,
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-0",
            "messages": [{"role": "user", "content": "What's the weather in NYC?"}],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                }
            ],
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stop_reason"] == "tool_use"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "tool_use"
    assert data["content"][0]["name"] == "get_weather"
    assert data["content"][0]["input"] == {"location": "NYC"}


@respx.mock
def test_ollama_with_thinking():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(
            200,
            json={
                "model": "qwen3.6:35b-a3b-coding-nvfp4",
                "created_at": "2024-01-01T00:00:00Z",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "The answer is 42.",
                    "thinking": "Let me think about this...",
                },
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-0",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["content"]) == 2
    assert data["content"][0]["type"] == "thinking"
    assert data["content"][0]["thinking"] == "Let me think about this..."
    assert data["content"][1]["type"] == "text"
    assert data["content"][1]["text"] == "The answer is 42."


@respx.mock
def test_ollama_upstream_error():
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(502, json={"error": "model not found"})
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-sonnet-4-0",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 502
    data = resp.json()
    assert data["type"] == "error"
    assert data["error"]["type"] == "api_error"


# ---------------------------------------------------------------------------
# SiliconFlow e2e tests
# ---------------------------------------------------------------------------


@respx.mock
def test_siliconflow_non_streaming_text():
    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-sf-1",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "MiniMaxAI/MiniMax-M2.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from SiliconFlow!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-minimax-m2.5",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "siliconflow-minimax-m2.5"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "text"
    assert data["content"][0]["text"] == "Hello from SiliconFlow!"
    assert data["stop_reason"] == "end_turn"
    assert data["usage"]["input_tokens"] == 10
    assert data["usage"]["output_tokens"] == 5

    # Verify the upstream request
    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "MiniMaxAI/MiniMax-M2.5"
    assert upstream["messages"][0]["role"] == "user"


@respx.mock
def test_siliconflow_streaming_text():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-sf-2",
                "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-sf-2",
                "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
            }
        ),
    ]

    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-minimax-m2.5",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream"

    events = _parse_sse(resp.text)
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "siliconflow-minimax-m2.5"

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 2
    assert text_deltas[0][1]["delta"]["text"] == "Hello"
    assert text_deltas[1][1]["delta"]["text"] == " world"

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"
    assert events[-1][0] == "message_stop"


@respx.mock
def test_siliconflow_with_reasoning():
    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-sf-3",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "moonshotai/Kimi-K2.6",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                            "reasoning_content": "Let me think...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-kimi-k2.6",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "siliconflow-kimi-k2.6"
    assert len(data["content"]) == 2
    assert data["content"][0]["type"] == "thinking"
    assert data["content"][0]["thinking"] == "Let me think..."
    assert data["content"][0]["signature"] == ""
    assert data["content"][1]["type"] == "text"
    assert data["content"][1]["text"] == "The answer is 42."


@respx.mock
def test_siliconflow_streaming_with_reasoning():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-sf-4",
                "choices": [{"delta": {"reasoning_content": "Let me"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-sf-4",
                "choices": [{"delta": {"reasoning_content": " think..."}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-sf-4",
                "choices": [{"delta": {"content": "42"}, "finish_reason": "stop"}],
            }
        ),
    ]

    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-kimi-k2.6",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    thinking_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "thinking_delta"
    ]
    assert len(thinking_deltas) == 2
    assert thinking_deltas[0][1]["delta"]["thinking"] == "Let me"
    assert thinking_deltas[1][1]["delta"]["thinking"] == " think..."

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 1
    assert text_deltas[0][1]["delta"]["text"] == "42"

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"


@respx.mock
def test_siliconflow_streaming_tool_calls():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-sf-5",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "get_weather", "arguments": ""},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-sf-5",
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": '{"location": "'}}
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-sf-5",
                "choices": [
                    {
                        "delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'NYC"}'}}]},
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        ),
    ]

    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-kimi-k2.6",
            "messages": [{"role": "user", "content": "Weather in NYC?"}],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                }
            ],
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    tool_starts = [
        e
        for e in events
        if e[0] == "content_block_start" and e[1]["content_block"]["type"] == "tool_use"
    ]
    assert len(tool_starts) == 1
    assert tool_starts[0][1]["content_block"]["name"] == "get_weather"

    json_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "input_json_delta"
    ]
    assert len(json_deltas) == 2
    assert json_deltas[0][1]["delta"]["partial_json"] == '{"location": "'
    assert json_deltas[1][1]["delta"]["partial_json"] == 'NYC"}'

    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "tool_use"


@respx.mock
def test_siliconflow_upstream_error():
    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            429,
            json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-minimax-m2.5",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 429
    data = resp.json()
    assert data["type"] == "error"
    assert data["error"]["type"] == "rate_limit_error"


@respx.mock
@respx.mock
def test_siliconflow_strips_images_when_fallback_disabled(monkeypatch):
    """Non-vision backends strip images and continue when fallback is disabled."""
    monkeypatch.setattr(settings, "vision_fallback_enabled", False)
    route = respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-sf-sr",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "MiniMaxAI/MiniMax-M2.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "I see text."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-minimax-m2.5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this:"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "abc123",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["content"][0]["text"] == "I see text."

    # Verify the image was stripped from the upstream request
    upstream_body = json.loads(route.calls.last.request.content)
    user_msg = upstream_body["messages"][0]
    assert user_msg["role"] == "user"
    assert "[image]" in str(user_msg["content"])


@respx.mock
def test_siliconflow_thinking_passthrough():
    """Verify thinking/effort fields are sent to SiliconFlow."""
    route = respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-sf-6",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "moonshotai/Kimi-K2.6",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Thoughtful response.",
                            "reasoning_content": "Deep thinking...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-kimi-k2.6",
            "messages": [{"role": "user", "content": "Think hard"}],
            "max_tokens": 100,
            "thinking": {"type": "enabled"},
            "output_config": {"effort": "xhigh"},
            "stream": False,
        },
    )

    assert resp.status_code == 200

    # Verify upstream received enable_thinking + thinking_budget
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["enable_thinking"] is True
    assert upstream["thinking_budget"] == 24576


@respx.mock
def test_siliconflow_thinking_disabled():
    """Verify thinking=disabled is passed through."""
    route = respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-sf-7",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "zai-org/GLM-5.1",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Straight answer."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-glm-5.1",
            "messages": [{"role": "user", "content": "Quick answer"}],
            "max_tokens": 100,
            "thinking": {"type": "disabled"},
            "stream": False,
        },
    )

    assert resp.status_code == 200

    upstream = json.loads(route.calls[0].request.content)
    assert upstream["enable_thinking"] is False


@respx.mock
def test_siliconflow_streaming_error():
    """Upstream errors during streaming are sent as in-stream SSE error events."""
    respx.post("https://api.siliconflow.com/v1/chat/completions").mock(
        return_value=Response(
            503,
            text='{"error": {"message": "Service overloaded"}}',
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "siliconflow-minimax-m2.5",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    error_events = [e for e in events if e[0] == "error"]
    assert len(error_events) == 1
    assert error_events[0][1]["error"]["type"] == "overloaded_error"
    assert error_events[0][1]["error"]["status_code"] == 503


# ---------------------------------------------------------------------------
# Fireworks AI e2e tests
# ---------------------------------------------------------------------------

_FW_BASE = "https://api.fireworks.ai/inference/v1/chat/completions"


@respx.mock
def test_fireworks_non_streaming_text():
    respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-1",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/kimi-k2p6",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from Fireworks!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "fireworks-kimi-k2p6"
    assert data["content"][0]["type"] == "text"
    assert data["content"][0]["text"] == "Hello from Fireworks!"
    assert data["stop_reason"] == "end_turn"
    assert data["usage"]["input_tokens"] == 10
    assert data["usage"]["output_tokens"] == 5

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "accounts/fireworks/models/kimi-k2p6"


@respx.mock
def test_fireworks_streaming_text():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-fw-2",
                "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-fw-2",
                "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
            }
        ),
    ]

    respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "fireworks-kimi-k2p6"

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 2
    assert text_deltas[0][1]["delta"]["text"] == "Hello"
    assert text_deltas[1][1]["delta"]["text"] == " world"
    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"


@respx.mock
def test_fireworks_with_reasoning():
    respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-3",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/kimi-k2p6",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                            "reasoning_content": "Let me think...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["content"]) == 2
    assert data["content"][0]["type"] == "thinking"
    assert data["content"][0]["thinking"] == "Let me think..."
    assert data["content"][0]["signature"] == ""
    assert data["content"][1]["type"] == "text"
    assert data["content"][1]["text"] == "The answer is 42."


@respx.mock
def test_fireworks_streaming_with_reasoning():
    chunks = [
        json.dumps(
            {
                "id": "chatcmpl-fw-4",
                "choices": [{"delta": {"reasoning_content": "Let me"}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-fw-4",
                "choices": [{"delta": {"reasoning_content": " think..."}, "finish_reason": None}],
            }
        ),
        json.dumps(
            {
                "id": "chatcmpl-fw-4",
                "choices": [{"delta": {"content": "42"}, "finish_reason": "stop"}],
            }
        ),
    ]

    respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            text="".join(f"data:{c}\n\n" for c in chunks) + "data:[DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    thinking_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "thinking_delta"
    ]
    assert len(thinking_deltas) == 2
    assert thinking_deltas[0][1]["delta"]["thinking"] == "Let me"
    assert thinking_deltas[1][1]["delta"]["thinking"] == " think..."

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert len(text_deltas) == 1
    assert text_deltas[0][1]["delta"]["text"] == "42"
    assert events[-2][0] == "message_delta"
    assert events[-2][1]["delta"]["stop_reason"] == "end_turn"


@respx.mock
def test_fireworks_tool_call_non_streaming():
    respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-5",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/kimi-k2p6",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"location": "NYC"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                }
            ],
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["stop_reason"] == "tool_use"
    assert data["content"][0]["type"] == "tool_use"
    assert data["content"][0]["name"] == "get_weather"
    assert data["content"][0]["input"] == {"location": "NYC"}


@respx.mock
def test_fireworks_upstream_error():
    respx.post(_FW_BASE).mock(
        return_value=Response(
            429,
            json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 429
    data = resp.json()
    assert data["type"] == "error"
    assert data["error"]["type"] == "rate_limit_error"


@respx.mock
def test_fireworks_thinking_passthrough():
    """Verify Anthropic-compatible thinking object is sent to Fireworks."""
    route = respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-7",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/kimi-k2p6",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Thoughtful response.",
                            "reasoning_content": "Deep thinking...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "Think hard"}],
            "max_tokens": 100,
            "thinking": {"type": "enabled"},
            "stream": False,
        },
    )

    assert resp.status_code == 200
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["thinking"] == {"type": "enabled"}
    assert "enable_thinking" not in upstream
    assert "thinking_budget" not in upstream


@respx.mock
def test_fireworks_thinking_disabled():
    """Verify thinking=disabled is passed through to Fireworks."""
    route = respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-8",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/kimi-k2p6",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Straight answer."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-kimi-k2p6",
            "messages": [{"role": "user", "content": "Quick answer"}],
            "max_tokens": 100,
            "thinking": {"type": "disabled"},
            "stream": False,
        },
    )

    assert resp.status_code == 200
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["thinking"] == {"type": "disabled"}
    assert "enable_thinking" not in upstream


@respx.mock
@respx.mock
def test_fireworks_strips_images_when_fallback_disabled(monkeypatch):
    """Non-vision backends strip images and continue when fallback is disabled."""
    monkeypatch.setattr(settings, "vision_fallback_enabled", False)
    route = respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-sr",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/minimax-m2p7",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "I see text."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-minimax-m2p7",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this:"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "abc123",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["content"][0]["text"] == "I see text."

    # Verify the image was stripped from the upstream request
    upstream_body = json.loads(route.calls.last.request.content)
    user_msg = upstream_body["messages"][0]
    assert user_msg["role"] == "user"
    assert "[image]" in str(user_msg["content"])


@respx.mock
def test_fireworks_minimax_non_streaming():
    respx.post(_FW_BASE).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-fw-6",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "accounts/fireworks/models/minimax-m2p7",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from MiniMax!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "fireworks-minimax-m2p7",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "fireworks-minimax-m2p7"
    assert data["content"][0]["text"] == "Hello from MiniMax!"

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "accounts/fireworks/models/minimax-m2p7"


# ---------------------------------------------------------------------------
# MiMo e2e tests (Anthropic-native passthrough)
# ---------------------------------------------------------------------------


@respx.mock
def test_mimo_non_streaming_text():
    respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_mimo_1",
                "type": "message",
                "role": "assistant",
                "model": "mimo-v2.5-pro",
                "content": [{"type": "text", "text": "Hello from MiMo!"}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "mimo-v2.5-pro",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "mimo-v2.5-pro"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "text"
    assert data["content"][0]["text"] == "Hello from MiMo!"
    assert data["stop_reason"] == "end_turn"
    assert data["usage"]["input_tokens"] == 10
    assert data["usage"]["output_tokens"] == 5

    # Verify the upstream request
    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "mimo-v2.5-pro"
    assert upstream["messages"][0]["role"] == "user"
    assert respx.routes[0].calls[0].request.headers["api-key"] == "test-mimo-key"


def _make_sse(event_type, data):
    """Format an SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@respx.mock
def test_mimo_streaming_text():
    sse_body = (
        _make_sse(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_mimo_2",
                    "type": "message",
                    "role": "assistant",
                    "model": "mimo-v2.5-pro",
                    "content": [],
                    "stop_reason": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
        )
        + _make_sse(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello"},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": " world"},
            },
        )
        + _make_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        + _make_sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )
        + _make_sse("message_stop", {"type": "message_stop"})
    )

    respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            text=sse_body,
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "mimo-v2.5-pro",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream"

    events = _parse_sse(resp.text)
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "mimo-v2.5-pro"

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert "".join(d[1]["delta"]["text"] for d in text_deltas) == "Hello world"

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "mimo-v2.5-pro"
    assert upstream["stream"] is True
    assert respx.routes[0].calls[0].request.headers["api-key"] == "test-mimo-key"


@respx.mock
def test_mimo_with_reasoning():
    """Anthropic passthrough: thinking blocks pass through natively."""
    respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_mimo_3",
                "type": "message",
                "role": "assistant",
                "model": "mimo-v2.5-pro",
                "content": [
                    {"type": "thinking", "thinking": "The user is greeting me.", "signature": ""},
                    {"type": "text", "text": "Hello!"},
                ],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 8,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "mimo-v2.5-pro",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "mimo-v2.5-pro"
    assert len(data["content"]) == 2
    assert data["content"][0]["type"] == "thinking"
    assert data["content"][0]["thinking"] == "The user is greeting me."
    assert data["content"][1]["type"] == "text"
    assert data["content"][1]["text"] == "Hello!"


@respx.mock
def test_mimo_streaming_with_reasoning():
    """Anthropic passthrough streaming preserves thinking deltas."""
    sse_body = (
        _make_sse(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_mimo_4",
                    "type": "message",
                    "role": "assistant",
                    "model": "mimo-v2.5-pro",
                    "content": [],
                    "stop_reason": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
        )
        + _make_sse(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": "", "signature": ""},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "The user"},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": " wants a greeting."},
            },
        )
        + _make_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        + _make_sse(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {"type": "text", "text": ""},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": "Hello"},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": " there!"},
            },
        )
        + _make_sse("content_block_stop", {"type": "content_block_stop", "index": 1})
        + _make_sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"input_tokens": 10, "output_tokens": 8},
            },
        )
        + _make_sse("message_stop", {"type": "message_stop"})
    )

    respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            text=sse_body,
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "mimo-v2.5-pro",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    thinking_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "thinking_delta"
    ]
    assert "".join(d[1]["delta"]["thinking"] for d in thinking_deltas) == (
        "The user wants a greeting."
    )

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert "".join(d[1]["delta"]["text"] for d in text_deltas) == "Hello there!"


@respx.mock
def test_mimo_with_cache_control():
    """Anthropic passthrough preserves cache_control breakpoints in the request."""
    route = respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_mimo_5",
                "type": "message",
                "role": "assistant",
                "model": "mimo-v2.5-pro",
                "content": [{"type": "text", "text": "Cached response"}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_input_tokens": 8,
                    "cache_creation_input_tokens": 0,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "model": "mimo-v2.5-pro",
            "system": [
                {
                    "type": "text",
                    "text": "Cached system prompt.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["usage"]["cache_read_input_tokens"] == 8

    upstream = json.loads(route.calls[0].request.content)
    assert upstream["system"][0]["cache_control"]["type"] == "ephemeral", (
        "cache_control breakpoint preserved in passthrough"
    )


@respx.mock
def test_mimo_v2_5_base_model():
    """Verify the base mimo-v2.5 model routes correctly with Anthropic passthrough."""
    respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_mimo_6",
                "type": "message",
                "role": "assistant",
                "model": "mimo-v2.5",
                "content": [{"type": "text", "text": "Hello from MiMo v2.5!"}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "mimo-v2.5",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "mimo-v2.5"
    assert data["content"][0]["text"] == "Hello from MiMo v2.5!"

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "mimo-v2.5"


@respx.mock
def test_mimo_upstream_error_mapping():
    respx.post("https://token-plan-sgp.xiaomimimo.com/anthropic/v1/messages").mock(
        return_value=Response(429, text="Too many requests"),
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "mimo-v2.5-pro",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
        },
    )

    assert resp.status_code == 429
    assert resp.json()["error"]["type"] == "rate_limit_error"


# ---------------------------------------------------------------------------
# Common e2e tests
# ---------------------------------------------------------------------------


def test_unknown_model():
    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "claude-unknown",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request_error"


def test_invalid_auth():
    resp = client.post(
        "/v1/messages",
        headers={"x-api-key": "wrong", "Content-Type": "application/json"},
        json={
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["type"] == "authentication_error"


# ---------------------------------------------------------------------------
# MiniMax e2e tests
# ---------------------------------------------------------------------------


@respx.mock
def test_minimax_non_streaming_text():
    respx.post("https://api.minimax.io/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_minimax_1",
                "type": "message",
                "role": "assistant",
                "model": "MiniMax-M2.7",
                "content": [{"type": "text", "text": "Hello from MiniMax!"}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "minimax-m2.7",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "MiniMax-M2.7"
    assert len(data["content"]) == 1
    assert data["content"][0]["type"] == "text"
    assert data["content"][0]["text"] == "Hello from MiniMax!"
    assert data["stop_reason"] == "end_turn"
    assert data["usage"]["input_tokens"] == 10
    assert data["usage"]["output_tokens"] == 5
    assert data["usage"]["cache_read_input_tokens"] == 0
    assert data["usage"]["cache_creation_input_tokens"] == 0

    # Verify the upstream request
    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "MiniMax-M2.7"
    assert upstream["messages"][0]["role"] == "user"
    assert respx.routes[0].calls[0].request.headers["Authorization"] == "Bearer test-minimax-key"


@respx.mock
def test_minimax_non_streaming_null_content():
    """MiniMax may return content: null on edge cases; bridge normalizes to [].\
\
\
    Regression test for the case where MiniMax returns a well-formed 200 response
    with content: null instead of content: [].
    """
    respx.post("https://api.minimax.io/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_minimax_null",
                "type": "message",
                "role": "assistant",
                "model": "MiniMax-M3",
                "content": None,  # MiniMax can return null on truncated/edge responses
                "stop_reason": "max_tokens",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "minimax-m3",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert data["model"] == "MiniMax-M3"
    assert data["content"] == []
    assert data["stop_reason"] == "max_tokens"


@respx.mock
def test_minimax_passthrough_system_role_message():
    """System-role messages pass through unchanged to MiniMax."""
    respx.post("https://api.minimax.io/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_minimax_sysrole",
                "type": "message",
                "role": "assistant",
                "model": "MiniMax-M3",
                "content": [{"type": "text", "text": "Acknowledged."}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 5,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "minimax-m3",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "system", "content": "System note mid-conversation"},
                {"role": "assistant", "content": "OK"},
            ],
            "max_tokens": 100,
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"][0]["text"] == "Acknowledged."

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "MiniMax-M3"
    assert len(upstream["messages"]) == 3
    assert upstream["messages"][1]["role"] == "system"
    assert upstream["messages"][1]["content"] == "System note mid-conversation"


@respx.mock
def test_minimax_non_streaming_with_cache_hit():
    """MiniMax explicit caching: second request should show cache_read > 0."""
    respx.post("https://api.minimax.io/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_minimax_2",
                "type": "message",
                "role": "assistant",
                "model": "MiniMax-M2.7",
                "content": [{"type": "text", "text": "Cached response!"}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 21,
                    "output_tokens": 393,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 188086,
                },
            },
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "minimax-m2.7",
            "max_tokens": 1024,
            "system": [
                {
                    "type": "text",
                    "text": "You are a helpful assistant.",
                },
                {
                    "type": "text",
                    "text": "Pride and Prejudice full text here...",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            "messages": [{"role": "user", "content": "Analyze the major themes."}],
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"][0]["text"] == "Cached response!"
    assert data["usage"]["cache_read_input_tokens"] == 188086
    assert data["usage"]["cache_creation_input_tokens"] == 0

    # Verify cache_control was forwarded to upstream
    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["system"][1]["cache_control"] == {"type": "ephemeral"}


@respx.mock
def test_minimax_streaming_text():
    sse_body = (
        _make_sse(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_minimax_3",
                    "type": "message",
                    "role": "assistant",
                    "model": "MiniMax-M2.7",
                    "content": [],
                    "stop_reason": None,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                },
            },
        )
        + _make_sse(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello"},
            },
        )
        + _make_sse(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": " world"},
            },
        )
        + _make_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        + _make_sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_creation_input_tokens": 100,
                    "cache_read_input_tokens": 50,
                },
            },
        )
        + _make_sse("message_stop", {"type": "message_stop"})
    )

    respx.post("https://api.minimax.io/anthropic/v1/messages").mock(
        return_value=Response(
            200,
            text=sse_body,
            headers={"Content-Type": "text/event-stream"},
        )
    )

    resp = client.post(
        "/v1/messages",
        headers=_auth_headers(),
        json={
            "model": "minimax-m2.7",
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream"

    events = _parse_sse(resp.text)
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "MiniMax-M2.7"

    text_deltas = [
        e
        for e in events
        if e[0] == "content_block_delta" and e[1]["delta"].get("type") == "text_delta"
    ]
    assert "".join(d[1]["delta"]["text"] for d in text_deltas) == "Hello world"

    upstream = json.loads(respx.routes[0].calls[0].request.content)
    assert upstream["model"] == "MiniMax-M2.7"
    assert upstream["stream"] is True
    assert respx.routes[0].calls[0].request.headers["Authorization"] == "Bearer test-minimax-key"


def test_list_models():
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    model_ids = {m["id"] for m in data["data"]}
    assert "claude-opus-4-6" in model_ids
    assert "claude-sonnet-4-6" in model_ids
    assert "claude-haiku-4-5" in model_ids
    assert "claude-sonnet-4-0" in model_ids
    assert "claude-haiku-4-0" in model_ids
    assert "ollama-sonnet" in model_ids
    assert "ollama-haiku" in model_ids
    assert "ollama-gpt-oss" in model_ids
    assert "ollama-gemma" in model_ids
    assert "siliconflow-minimax-m2.5" in model_ids
    assert "siliconflow-kimi-k2.6" in model_ids
    assert "siliconflow-glm-5.1" in model_ids
    assert "fireworks-kimi-k2p6" in model_ids
    assert "fireworks-minimax-m2p7" in model_ids
    assert "mimo-v2.5-pro" in model_ids
    assert "mimo-v2.5" in model_ids
    assert "minimax-m2.7" in model_ids


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse SSE text into list of (event_type, data_dict)."""
    events = []
    for raw_event in text.strip().split("\n\n"):
        if not raw_event.strip():
            continue
        lines = raw_event.strip().split("\n")
        event_type = lines[0].replace("event: ", "")
        data = json.loads(lines[1].replace("data: ", ""))
        events.append((event_type, data))
    return events
