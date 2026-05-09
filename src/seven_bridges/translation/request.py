"""Anthropic Messages API → OpenAI Chat Completions request translation."""

import json
from typing import Any, Literal, cast

from seven_bridges.models.anthropic import (
    ContentBlock,
    ImageBlock,
    Message,
    MessagesRequest,
    TextBlock,
    ThinkingBlock,
    Tool,
    ToolResultBlock,
    ToolUseBlock,
)
from seven_bridges.models.openai import (
    ChatCompletionRequest,
    ChatCompletionTool,
    FunctionDefinition,
)


def _anthropic_image_to_openai(image_block: ImageBlock) -> dict[str, Any] | None:
    """Convert an Anthropic ImageBlock to OpenAI image_url format."""
    source = image_block.source
    if not isinstance(source, dict):
        return None
    source_type = source.get("type")
    if source_type == "base64":
        media_type = source.get("media_type", "image/jpeg")
        data = source.get("data", "")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{data}"},
        }
    return None


def _convert_user_content(content: str | list[ContentBlock]) -> str | list[dict[str, Any]]:
    """Convert Anthropic user message content to OpenAI format.

    Returns a string for text-only content, or a list of content parts
    for mixed content (text + images).
    """
    if isinstance(content, str):
        return content

    parts: list[dict[str, Any]] = []
    has_images = False

    for block in content:
        if isinstance(block, TextBlock):
            parts.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageBlock):
            img = _anthropic_image_to_openai(block)
            if img:
                parts.append(img)
                has_images = True
        elif isinstance(block, ToolResultBlock):
            # Tool results become text describing the result
            tool_content = block.content
            if isinstance(tool_content, list):
                tool_parts: list[str] = []
                for item in tool_content:
                    if isinstance(item, TextBlock):
                        tool_parts.append(item.text)
                    elif isinstance(item, ImageBlock):
                        img = _anthropic_image_to_openai(item)
                        if img:
                            url = img["image_url"]["url"]
                            tool_parts.append(f"[Image: {url[:80]}...]")
                tool_text = "\n".join(tool_parts)
            else:
                tool_text = tool_content or ""
            parts.append(
                {
                    "type": "text",
                    "text": f"<tool_result id={block.tool_use_id}>\n{tool_text}\n</tool_result>",
                }
            )
        elif isinstance(block, ToolUseBlock):
            args = json.dumps(block.input)
            parts.append(
                {
                    "type": "text",
                    "text": f"<tool_use id={block.id} name={block.name}>\n{args}\n</tool_use>",
                }
            )
        elif isinstance(block, ThinkingBlock):
            # Don't render thinking in content string; it's handled separately
            pass

    # If there are no images, collapse to a plain string for broader compatibility
    if not has_images and parts:
        text_only = "\n".join(p["text"] for p in parts if p.get("type") == "text")
        return text_only

    return parts


def _convert_assistant_content(
    content: str | list[ContentBlock],
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Convert Anthropic assistant message content to OpenAI format.

    Returns (text_content, tool_calls, reasoning_content).
    """
    if isinstance(content, str):
        return content, [], None

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    reasoning_content: str | None = None

    for block in content:
        if isinstance(block, TextBlock):
            text_parts.append(block.text)
        elif isinstance(block, ToolUseBlock):
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    },
                }
            )
        elif isinstance(block, ThinkingBlock):
            reasoning_content = block.thinking
        # Images in assistant messages are not supported by OpenAI

    return "\n".join(text_parts), tool_calls, reasoning_content


def _convert_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert Anthropic messages to OpenAI message dicts."""
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "user":
            content = _convert_user_content(msg.content)
            result.append({"role": "user", "content": content})
        elif msg.role == "assistant":
            text_content, tool_calls, reasoning_content = _convert_assistant_content(msg.content)

            openai_msg: dict[str, Any] = {"role": "assistant"}
            if text_content:
                openai_msg["content"] = text_content
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls
            if reasoning_content:
                openai_msg["reasoning_content"] = reasoning_content

            result.append(openai_msg)
    return result


def request_has_images(request: MessagesRequest) -> bool:
    """Check if the request contains any image blocks."""
    for msg in request.messages:
        if isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, ImageBlock):
                    return True
                if isinstance(block, ToolResultBlock) and isinstance(block.content, list):
                    for item in block.content:
                        if isinstance(item, ImageBlock):
                            return True
    return False


def _convert_tools(tools: list[Tool] | None) -> list[ChatCompletionTool] | None:
    """Convert Anthropic tools to OpenAI tool format."""
    if not tools:
        return None
    return [
        ChatCompletionTool(
            function=FunctionDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema.model_dump(exclude_none=True)
                if tool.input_schema
                else None,
            )
        )
        for tool in tools
    ]


def _convert_tool_choice(tool_choice: str | dict[str, Any] | None) -> str | dict[str, Any] | None:
    """Convert Anthropic tool_choice to OpenAI format."""
    if tool_choice is None:
        return None
    if tool_choice == "auto":
        return "auto"
    if tool_choice == "none":
        return "none"
    if tool_choice == "any":
        return "required"
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    return None


def anthropic_to_openai(
    request: MessagesRequest,
    backend_name: str,
) -> ChatCompletionRequest:
    """Translate an Anthropic MessagesRequest to an OpenAI ChatCompletionRequest."""
    messages: list[dict[str, Any]] = []

    # System prompt goes first as a system message
    if request.system:
        if isinstance(request.system, str):
            messages.append({"role": "system", "content": request.system})
        else:
            system_text = "\n".join(
                block.text for block in request.system if isinstance(block, TextBlock)
            )
            if system_text:
                messages.append({"role": "system", "content": system_text})

    # Convert conversation messages
    messages.extend(_convert_messages(request.messages))

    # Build OpenAI request
    return ChatCompletionRequest(
        model=request.model,
        messages=messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        stop=request.stop_sequences,
        stream=request.stream or False,
        tools=_convert_tools(request.tools),
        tool_choice=cast(
            "Literal['none', 'auto', 'required'] | dict[str, Any] | None",
            _convert_tool_choice(request.tool_choice),
        ),
    )
