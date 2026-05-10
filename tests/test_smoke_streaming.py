"""Live streaming smoke test — hits real upstream APIs.

Requires:
- Bridge running on localhost:4001
- Valid DEEPSEEK_API_KEY and KIMI_CODE_API_KEY

Run:
    uv run pytest tests/test_smoke_streaming.py -v
"""

import json
import os

import httpx
import pytest

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:4001")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "ollama")


def _bridge_is_healthy() -> bool:
    try:
        r = httpx.get(f"{BRIDGE_URL}/health", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _bridge_is_healthy(),
    reason=f"Bridge not reachable at {BRIDGE_URL}",
)


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse SSE response text into (event_type, data) tuples."""
    events = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("event:"):
            event_type = line[6:].strip()
            i += 1
            if i < len(lines) and lines[i].strip().startswith("data:"):
                data = lines[i].strip()[5:].strip()
                i += 1
                if data == "[DONE]" or not data:
                    continue
                events.append((event_type, json.loads(data)))
            else:
                # Malformed: event line without data line
                i += 1
        elif line.startswith("data:"):
            # Standalone data line (no event prefix)
            data = line[5:].strip()
            i += 1
            if data == "[DONE]" or not data:
                continue
            events.append(("data", json.loads(data)))
        else:
            i += 1
    return events


@pytest.mark.parametrize(
    "model_alias",
    ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-6"],
)
def test_live_streaming_smoke(model_alias: str) -> None:
    """Verify streaming works end-to-end for each model tier."""
    resp = httpx.post(
        f"{BRIDGE_URL}/v1/messages",
        headers={
            "x-api-key": BRIDGE_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "model": model_alias,
            "messages": [{"role": "user", "content": "Say 'hello' and nothing else."}],
            "max_tokens": 50,
            "stream": True,
        },
        timeout=60.0,
    )
    assert resp.status_code == 200, f"{model_alias}: HTTP {resp.status_code}"
    assert "text/event-stream" in resp.headers.get("content-type", "")

    events = _parse_sse(resp.text)

    # Must have at least message_start + some content + message_stop
    event_types = [e[0] for e in events]
    assert "message_start" in event_types, f"{model_alias}: missing message_start"

    # Should have at least one content block delta
    content_deltas = [e for e in events if e[1].get("type") == "content_block_delta"]
    assert len(content_deltas) > 0, f"{model_alias}: no content deltas"

    # Final event should be message_stop or a finish event
    assert any(e[1].get("type") in ("message_stop", "message_delta") for e in events), (
        f"{model_alias}: no termination event"
    )

    # Response should contain "hello" (case-insensitive)
    all_text = ""
    for e in events:
        delta = e[1].get("delta", {})
        if delta.get("type") == "text_delta":
            all_text += delta.get("text", "")
        elif delta.get("type") == "thinking_delta":
            all_text += delta.get("thinking", "")

    assert "hello" in all_text.lower(), f"{model_alias}: response '{all_text}' missing 'hello'"
