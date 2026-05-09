"""Unit tests for OpenAI SSE → Anthropic SSE streaming translation."""

import json

import pytest

from seven_bridges.translation.stream import translate_openai_stream


@pytest.mark.anyio
async def _collect_stream(stream):
    """Helper to collect all SSE events from an async stream."""
    events = []
    async for event in stream:
        # Parse each SSE event (format: "event: <type>\ndata: <json>\n\n")
        lines = event.strip().split("\n")
        event_type = lines[0].replace("event: ", "")
        data = json.loads(lines[1].replace("data: ", ""))
        events.append((event_type, data))
    return events


@pytest.mark.anyio
async def test_stream_text_only():
    async def raw_stream():
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
                }
            ),
        }
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}],
                }
            ),
        }

    events = await _collect_stream(translate_openai_stream(raw_stream(), "claude-sonnet-4-6"))

    # message_start
    assert events[0][0] == "message_start"
    assert events[0][1]["message"]["model"] == "claude-sonnet-4-6"
    assert events[0][1]["message"]["id"] != ""  # Should have a UUID

    # content_block_start for text
    assert events[1][0] == "content_block_start"
    assert events[1][1]["content_block"]["type"] == "text"

    # content_block_delta x2
    assert events[2][0] == "content_block_delta"
    assert events[2][1]["delta"]["text"] == "Hello"
    assert events[3][0] == "content_block_delta"
    assert events[3][1]["delta"]["text"] == " world"

    # content_block_stop
    assert events[4][0] == "content_block_stop"

    # message_delta
    assert events[5][0] == "message_delta"
    assert events[5][1]["delta"]["stop_reason"] == "end_turn"

    # message_stop
    assert events[6][0] == "message_stop"


@pytest.mark.anyio
async def test_stream_reasoning_then_content():
    async def raw_stream():
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [{"delta": {"reasoning_content": "Let me"}, "finish_reason": None}],
                }
            ),
        }
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [
                        {"delta": {"reasoning_content": " think..."}, "finish_reason": None}
                    ],
                }
            ),
        }
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [{"delta": {"content": "Answer: 42"}, "finish_reason": "stop"}],
                }
            ),
        }

    events = await _collect_stream(translate_openai_stream(raw_stream(), "claude-opus-4-6"))

    # message_start
    assert events[0][0] == "message_start"

    # thinking block start
    assert events[1][0] == "content_block_start"
    assert events[1][1]["content_block"]["type"] == "thinking"
    assert events[1][1]["content_block"]["signature"] == ""

    # thinking deltas
    assert events[2][0] == "content_block_delta"
    assert events[2][1]["delta"]["thinking"] == "Let me"
    assert events[3][0] == "content_block_delta"
    assert events[3][1]["delta"]["thinking"] == " think..."

    # thinking block stop
    assert events[4][0] == "content_block_stop"

    # text block start
    assert events[5][0] == "content_block_start"
    assert events[5][1]["content_block"]["type"] == "text"

    # text delta
    assert events[6][0] == "content_block_delta"
    assert events[6][1]["delta"]["text"] == "Answer: 42"

    # text block stop
    assert events[7][0] == "content_block_stop"

    # message_delta
    assert events[8][0] == "message_delta"
    assert events[8][1]["delta"]["stop_reason"] == "end_turn"

    # message_stop
    assert events[9][0] == "message_stop"


@pytest.mark.anyio
async def test_stream_tool_calls():
    async def raw_stream():
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "get_weather", "arguments": ""},
                                    },
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }
            ),
        }
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {"index": 0, "function": {"arguments": '{"location": "'}},
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }
            ),
        }
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {"index": 0, "function": {"arguments": 'NYC"}'}},
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                }
            ),
        }

    events = await _collect_stream(translate_openai_stream(raw_stream(), "claude-sonnet-4-6"))

    # message_start
    assert events[0][0] == "message_start"

    # tool_use block start
    assert events[1][0] == "content_block_start"
    assert events[1][1]["content_block"]["type"] == "tool_use"
    assert events[1][1]["content_block"]["id"] == "call_1"
    assert events[1][1]["content_block"]["name"] == "get_weather"

    # input_json_delta x2
    assert events[2][0] == "content_block_delta"
    assert events[2][1]["delta"]["type"] == "input_json_delta"
    assert events[2][1]["delta"]["partial_json"] == '{"location": "'
    assert events[3][0] == "content_block_delta"
    assert events[3][1]["delta"]["partial_json"] == 'NYC"}'

    # content_block_stop
    assert events[4][0] == "content_block_stop"

    # message_delta
    assert events[5][0] == "message_delta"
    assert events[5][1]["delta"]["stop_reason"] == "tool_use"

    # message_stop
    assert events[6][0] == "message_stop"


@pytest.mark.anyio
async def test_stream_usage_only_chunk():
    async def raw_stream():
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [{"delta": {"content": "Hi"}, "finish_reason": None}],
                }
            ),
        }
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
                }
            ),
        }

    events = await _collect_stream(translate_openai_stream(raw_stream(), "claude-sonnet-4-6"))

    # Find message_delta event
    message_delta = [e for e in events if e[0] == "message_delta"][0]
    assert message_delta[1]["usage"]["input_tokens"] == 10
    assert message_delta[1]["usage"]["output_tokens"] == 1


@pytest.mark.anyio
async def test_stream_skips_done_and_empty():
    async def raw_stream():
        yield {"type": "raw", "data": "[DONE]"}
        yield {"type": "raw", "data": ""}
        yield {
            "type": "raw",
            "data": json.dumps(
                {
                    "id": "chatcmpl-123",
                    "choices": [{"delta": {"content": "Hi"}, "finish_reason": "stop"}],
                }
            ),
        }

    events = await _collect_stream(translate_openai_stream(raw_stream(), "claude-sonnet-4-6"))
    # Should still produce valid events despite [DONE] and empty lines
    assert events[0][0] == "message_start"
    assert events[-1][0] == "message_stop"
