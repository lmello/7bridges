"""OpenAI SSE stream → Anthropic SSE event translation."""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from seven_bridges.models.anthropic import _SIGNATURE_PLACEHOLDER


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
    message_id = str(uuid.uuid4())
    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    stop_reason: str | None = None

    # Track which block types are currently open and their indices
    open_block_type: str | None = None
    open_block_index: int = -1
    next_block_index = 0

    # Tool call tracking: maps tool_index -> {"id", "name", "arguments", "block_index"}
    tool_call_map: dict[int, dict[str, Any]] = {}

    # Send message_start with a skeleton message
    yield _make_sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": message_id,
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

        # Some providers attach usage to the final chunk that also contains choices
        usage = chunk.get("usage")
        if usage:
            input_tokens = usage.get("prompt_tokens", input_tokens)
            output_tokens = usage.get("completion_tokens", output_tokens)
            if usage.get("prompt_cache_hit_tokens"):
                cache_read = usage["prompt_cache_hit_tokens"]
            elif usage.get("cached_tokens"):
                cache_read = usage["cached_tokens"]

        delta = choices[0].get("delta", {})
        finish = choices[0].get("finish_reason")

        # Prefer upstream id if available, but keep our uuid as fallback
        if chunk.get("id"):
            message_id = chunk["id"]

        if finish:
            stop_reason = _map_stop_reason(finish)

        # Handle reasoning_content
        reasoning = delta.get("reasoning_content")
        if reasoning:
            if open_block_type != "thinking":
                # Close previous block if any
                if open_block_type is not None:
                    yield _make_sse(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": open_block_index},
                    )
                # Start thinking block
                open_block_index = next_block_index
                next_block_index += 1
                open_block_type = "thinking"
                yield _make_sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": open_block_index,
                        "content_block": {
                            "type": "thinking",
                            "thinking": "",
                            "signature": _SIGNATURE_PLACEHOLDER,
                        },
                    },
                )
            yield _make_sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": open_block_index,
                    "delta": {"type": "thinking_delta", "thinking": reasoning},
                },
            )

        # Handle content
        content = delta.get("content")
        if content:
            if open_block_type != "text":
                # Close previous block if any
                if open_block_type is not None:
                    yield _make_sse(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": open_block_index},
                    )
                # Start text block
                open_block_index = next_block_index
                next_block_index += 1
                open_block_type = "text"
                yield _make_sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": open_block_index,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
            yield _make_sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": open_block_index,
                    "delta": {"type": "text_delta", "text": content},
                },
            )

        # Handle tool_calls (streaming tool calls)
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                tc_index = tc.get("index", 0)
                tc_id = tc.get("id")
                tc_function = tc.get("function", {})
                tc_name = tc_function.get("name")
                tc_args = tc_function.get("arguments")

                if tc_index not in tool_call_map:
                    # Close previous block if any
                    if open_block_type is not None:
                        yield _make_sse(
                            "content_block_stop",
                            {"type": "content_block_stop", "index": open_block_index},
                        )
                    # New tool call starting
                    tool_call_map[tc_index] = {
                        "id": tc_id or "",
                        "name": tc_name or "",
                        "arguments": tc_args or "",
                        "block_index": next_block_index,
                    }
                    open_block_index = next_block_index
                    next_block_index += 1
                    open_block_type = "tool_use"
                    # Emit content_block_start
                    yield _make_sse(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": open_block_index,
                            "content_block": {
                                "type": "tool_use",
                                "id": tc_id or "",
                                "name": tc_name or "",
                                "input": {},
                            },
                        },
                    )
                else:
                    # Existing tool call receiving more data
                    tc_state = tool_call_map[tc_index]
                    if tc_id:
                        tc_state["id"] = tc_id
                    if tc_name:
                        tc_state["name"] = tc_name
                    if tc_args:
                        tc_state["arguments"] += tc_args
                        # Emit input_json_delta
                        yield _make_sse(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": tc_state["block_index"],
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": tc_args,
                                },
                            },
                        )

    # Close any open block
    if open_block_type is not None:
        yield _make_sse(
            "content_block_stop",
            {"type": "content_block_stop", "index": open_block_index},
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
