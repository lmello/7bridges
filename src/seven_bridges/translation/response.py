"""OpenAI Chat Completions → Anthropic Messages API response translation."""

import json
from typing import Any

from seven_bridges.models.anthropic import (
    MessagesResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)
from seven_bridges.models.openai import ChatCompletionResponse, CompletionUsage


def _openai_finish_to_anthropic(finish_reason: str | None) -> str | None:
    """Map OpenAI finish_reason to Anthropic stop_reason."""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "max_tokens",
    }
    return mapping.get(finish_reason or "")


def _convert_usage(usage: CompletionUsage | None) -> Usage:
    """Convert OpenAI usage to Anthropic usage."""
    if usage is None:
        return Usage(input_tokens=0, output_tokens=0)

    cache_read = None
    if usage.prompt_cache_hit_tokens:
        cache_read = usage.prompt_cache_hit_tokens
    elif usage.cached_tokens:
        cache_read = usage.cached_tokens

    return Usage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        cache_read_input_tokens=cache_read,
    )


def openai_to_anthropic(data: dict[str, Any], model_alias: str) -> MessagesResponse:
    """Translate an OpenAI ChatCompletion response to Anthropic MessagesResponse."""
    response = ChatCompletionResponse.model_validate(data)
    choice = response.choices[0]
    msg = choice.message

    content: list[Any] = []

    # Reasoning content comes first (if present)
    if msg.reasoning_content:
        content.append(ThinkingBlock(thinking=msg.reasoning_content))

    # Main text content
    if msg.content:
        content.append(TextBlock(text=msg.content))

    # Tool calls
    if msg.tool_calls:
        for tc in msg.tool_calls:
            raw_args = tc["function"].get("arguments", "{}")
            try:
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                parsed_args = {}
            content.append(
                ToolUseBlock(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    input=parsed_args,
                )
            )

    return MessagesResponse(
        id=response.id,
        model=model_alias,
        content=content,
        stop_reason=_openai_finish_to_anthropic(choice.finish_reason),
        usage=_convert_usage(response.usage),
    )
