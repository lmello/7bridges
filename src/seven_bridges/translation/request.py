"""Anthropic Messages API → OpenAI Chat Completions request translation."""

from typing import Any

from seven_bridges.models.anthropic import (
    ContentBlock,
    Message,
    MessagesRequest,
    TextBlock,
    Tool,
    ToolResultBlock,
    ToolUseBlock,
)
from seven_bridges.models.openai import (
    ChatCompletionRequest,
    ChatCompletionTool,
    FunctionDefinition,
)


def _anthropic_content_to_str(content: str | list[ContentBlock]) -> str:
    """Convert Anthropic message content to a plain string for OpenAI."""
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, ToolResultBlock):
            # Tool results become text describing the result
            tool_content = block.content
            if isinstance(tool_content, list):
                tool_text = "\n".join(b.text for b in tool_content if isinstance(b, TextBlock))
            else:
                tool_text = tool_content or ""
            parts.append(f"<tool_result id={block.tool_use_id}>\n{tool_text}\n</tool_result>")
        elif isinstance(block, ToolUseBlock):
            parts.append(f"<tool_use id={block.id} name={block.name}>\n{block.input}\n</tool_use>")
        else:
            # Thinking blocks etc — drop them for OpenAI
            pass
    return "\n".join(parts)


def _convert_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert Anthropic messages to OpenAI message dicts."""
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "user":
            result.append({"role": "user", "content": _anthropic_content_to_str(msg.content)})
        elif msg.role == "assistant":
            content = _anthropic_content_to_str(msg.content)
            tool_calls: list[dict[str, Any]] = []
            reasoning_content: str | None = None

            if isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls.append(
                            {
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": block.input,
                                },
                            }
                        )
                    # Extract reasoning_content if present at top level or in provider fields
                    if isinstance(block, dict) and block.get("reasoning_content"):
                        reasoning_content = block["reasoning_content"]

            openai_msg: dict[str, Any] = {"role": "assistant"}
            if content:
                openai_msg["content"] = content
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls
            if reasoning_content:
                openai_msg["reasoning_content"] = reasoning_content

            result.append(openai_msg)
    return result


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


def _convert_tool_choice(
    tool_choice: str | dict[str, Any] | None
) -> str | dict[str, Any] | None:
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
        stop=request.stop_sequences,
        stream=request.stream or False,
        tools=_convert_tools(request.tools),
        tool_choice=_convert_tool_choice(request.tool_choice),
    )
