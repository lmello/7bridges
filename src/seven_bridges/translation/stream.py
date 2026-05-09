"""OpenAI SSE stream → Anthropic SSE event translation."""

import json
from collections.abc import AsyncIterator
from typing import Any


def _make_sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a dict as an SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def translate_openai_stream(
    openai_stream: AsyncIterator[dict[str, Any]],
    model_alias: str,
) -> AsyncIterator[str]:
    """Translate an OpenAI-style SSE stream to Anthropic-style SSE events.

    Yields formatted SSE strings ready to be sent to the client.
    """
    message_id = ""
    reasoning_started = False
    content_started = False
    reasoning_index = 0
    content_index = 1
    current_reasoning = ""
    current_content = ""
    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    stop_reason: str | None = None

    # Send message_start with a skeleton message
    yield _make_sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": "",
                "type": "message",
                "role": "assistant",
                "model": model_alias,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )

    async for event in openai_stream:
        raw_data = event.get("data", "")
        if not raw_data or raw_data == "[DONE]":
            continue

        try:
            chunk = json.loads(raw_data)
        except json.JSONDecodeError:
            continue

        choices = chunk.get("choices", [])
        if not choices:
            # Usage-only chunk (some providers send this at the end)
            usage = chunk.get("usage")
            if usage:
                input_tokens = usage.get("prompt_tokens", input_tokens)
                output_tokens = usage.get("completion_tokens", output_tokens)
                if usage.get("prompt_cache_hit_tokens"):
                    cache_read = usage["prompt_cache_hit_tokens"]
                elif usage.get("cached_tokens"):
                    cache_read = usage["cached_tokens"]
            continue

        delta = choices[0].get("delta", {})
        finish = choices[0].get("finish_reason")
        message_id = chunk.get("id", message_id)

        if finish:
            stop_reason = _map_stop_reason(finish)

        # Handle reasoning_content
        reasoning = delta.get("reasoning_content")
        if reasoning:
            if not reasoning_started:
                reasoning_started = True
                yield _make_sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": reasoning_index,
                        "content_block": {"type": "thinking", "thinking": ""},
                    },
                )
            current_reasoning += reasoning
            yield _make_sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": reasoning_index,
                    "delta": {"type": "thinking_delta", "thinking": reasoning},
                },
            )

        # Handle content
        content = delta.get("content")
        if content:
            if not content_started:
                content_started = True
                # If reasoning was ongoing, close it first
                if reasoning_started:
                    yield _make_sse(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": reasoning_index},
                    )
                yield _make_sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": content_index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
            current_content += content
            yield _make_sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": content_index,
                    "delta": {"type": "text_delta", "text": content},
                },
            )

        # Handle tool_calls (streaming tool calls)
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            # TODO: Implement streaming tool call translation
            pass

    # Close any open blocks
    if reasoning_started and not content_started:
        yield _make_sse(
            "content_block_stop",
            {"type": "content_block_stop", "index": reasoning_index},
        )
    elif content_started:
        yield _make_sse(
            "content_block_stop",
            {"type": "content_block_stop", "index": content_index},
        )

    # Send message_delta with usage
    yield _make_sse(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason},
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read if cache_read else None,
            },
        },
    )

    yield _make_sse("message_stop", {"type": "message_stop"})


def _map_stop_reason(finish: str | None) -> str | None:
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "max_tokens",
    }
    return mapping.get(finish or "")
