"""Unit tests for Anthropic ↔ OpenAI translation layer."""

import json

from seven_bridges.models.anthropic import (
    DocumentBlock,
    ImageBlock,
    Message,
    MessagesRequest,
    TextBlock,
    ThinkingBlock,
    Tool,
    ToolInputSchema,
    ToolResultBlock,
    ToolUseBlock,
)
from seven_bridges.translation.request import (
    _convert_assistant_content,
    _convert_user_content,
    anthropic_to_openai,
    request_has_images,
)
from seven_bridges.translation.response import openai_to_anthropic

# ---------------------------------------------------------------------------
# Request translation tests
# ---------------------------------------------------------------------------


def test_anthropic_to_openai_basic_text():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.model == "claude-opus-4-6"
    assert openai_req.messages == [{"role": "user", "content": "Hello"}]
    assert openai_req.max_tokens == 100
    assert openai_req.stream is False


def test_anthropic_to_openai_system_string():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hi")],
        system="You are helpful.",
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.messages[0] == {"role": "system", "content": "You are helpful."}
    assert openai_req.messages[1] == {"role": "user", "content": "Hi"}


def test_anthropic_to_openai_system_text_blocks():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hi")],
        system=[TextBlock(text="Be concise."), TextBlock(text="Be friendly.")],
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.messages[0] == {
        "role": "system",
        "content": "Be concise.\nBe friendly.",
    }


def test_anthropic_to_openai_system_role_message():
    """Mid-conversation system messages fold into a user message."""
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[
            Message(role="user", content="First msg"),
            Message(role="system", content="System note mid-conversation"),
            Message(role="assistant", content=[TextBlock(text="Response")]),
        ],
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.messages == [
        {"role": "user", "content": "First msg"},
        {"role": "user", "content": "System note mid-conversation"},
        {"role": "assistant", "content": "Response"},
    ]


def test_anthropic_to_openai_top_p_forwarded():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hi")],
        top_p=0.9,
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.top_p == 0.9


def test_anthropic_to_openai_tools_and_tool_choice():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="What's the weather?")],
        tools=[
            Tool(
                name="get_weather",
                description="Get weather",
                input_schema=ToolInputSchema(
                    properties={"location": {"type": "string"}},
                    required=["location"],
                ),
            )
        ],
        tool_choice="auto",
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.tools is not None
    assert len(openai_req.tools) == 1
    assert openai_req.tools[0].function.name == "get_weather"
    assert openai_req.tool_choice == "auto"


def test_anthropic_to_openai_tool_choice_any():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hi")],
        tool_choice="any",
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.tool_choice == "required"


def test_anthropic_to_openai_tool_choice_specific():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hi")],
        tool_choice={"type": "tool", "name": "get_weather"},
    )
    openai_req = anthropic_to_openai(req, "kimi")
    assert openai_req.tool_choice == {"type": "function", "function": {"name": "get_weather"}}


# ---------------------------------------------------------------------------
# Content block conversion tests
# ---------------------------------------------------------------------------


def test_convert_user_content_text_only():
    result = _convert_user_content("Hello")
    assert result == "Hello"


def test_convert_user_content_text_blocks():
    result = _convert_user_content([TextBlock(text="Hello"), TextBlock(text="World")])
    assert result == "Hello\nWorld"


def test_convert_user_content_with_image():
    result = _convert_user_content(
        [
            TextBlock(text="Describe this:"),
            ImageBlock(source={"type": "base64", "media_type": "image/jpeg", "data": "abc123"}),
        ]
    )
    assert isinstance(result, list)
    assert result[0] == {"type": "text", "text": "Describe this:"}
    assert result[1]["type"] == "image_url"
    assert result[1]["image_url"]["url"] == "data:image/jpeg;base64,abc123"


def test_convert_user_content_image_collapses_to_string_without_images():
    result = _convert_user_content([TextBlock(text="Hello")])
    assert result == "Hello"


def test_convert_user_content_tool_result():
    result = _convert_user_content(
        [
            ToolResultBlock(tool_use_id="call_1", content="The result is 42"),
        ]
    )
    assert "call_1" in result
    assert "The result is 42" in result


def test_convert_user_content_tool_result_with_images():
    result = _convert_user_content(
        [
            ToolResultBlock(
                tool_use_id="call_1",
                content=[
                    TextBlock(text="Here is the image:"),
                    ImageBlock(source={"type": "base64", "media_type": "image/png", "data": "xyz"}),
                ],
            ),
        ]
    )
    # Tool results are flattened to string for OpenAI compatibility
    assert isinstance(result, str)
    assert "call_1" in result
    assert "Here is the image:" in result
    assert "[Image: data:image/png;base64,xyz...]" in result


def test_convert_assistant_content_text_only():
    text, tool_calls, reasoning = _convert_assistant_content("Hello")
    assert text == "Hello"
    assert tool_calls == []
    assert reasoning is None


def test_convert_assistant_content_with_thinking():
    text, tool_calls, reasoning = _convert_assistant_content(
        [
            ThinkingBlock(thinking="Let me think..."),
            TextBlock(text="The answer is 42"),
        ]
    )
    assert text == "The answer is 42"
    assert reasoning == "Let me think..."
    assert tool_calls == []


def test_convert_assistant_content_with_tool_use():
    text, tool_calls, reasoning = _convert_assistant_content(
        [
            TextBlock(text="I'll check that."),
            ToolUseBlock(id="call_1", name="get_weather", input={"location": "NYC"}),
        ]
    )
    assert text == "I'll check that."
    assert len(tool_calls) == 1
    assert tool_calls[0]["id"] == "call_1"
    assert tool_calls[0]["function"]["name"] == "get_weather"
    assert json.loads(tool_calls[0]["function"]["arguments"]) == {"location": "NYC"}


# ---------------------------------------------------------------------------
# Image detection tests
# ---------------------------------------------------------------------------


def test_request_has_images_true():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    TextBlock(text="Describe:"),
                    ImageBlock(
                        source={"type": "base64", "media_type": "image/jpeg", "data": "abc"}
                    ),
                ],
            ),
        ],
    )
    assert request_has_images(req) is True


def test_request_has_images_false():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hello")],
    )
    assert request_has_images(req) is False


def test_convert_user_content_with_document():
    """Document blocks are converted to text placeholder in OpenAI translation."""
    result = _convert_user_content(
        [
            TextBlock(text="Analyze this:"),
            DocumentBlock(
                type="document",
                source={"type": "base64", "media_type": "application/pdf", "data": "aaaa"},
            ),
        ]
    )
    assert isinstance(result, list)
    assert result[0] == {"type": "text", "text": "Analyze this:"}
    assert result[1] == {"type": "text", "text": "[Document: application/pdf]"}


def test_convert_user_content_tool_result_with_document():
    """Documents in tool results become text placeholders."""
    result = _convert_user_content(
        [
            ToolResultBlock(
                tool_use_id="call_1",
                content=[
                    TextBlock(text="Here is the PDF:"),
                    DocumentBlock(
                        type="document",
                        source={"type": "base64", "media_type": "application/pdf", "data": "xyz"},
                    ),
                ],
            ),
        ]
    )
    assert isinstance(result, str)
    assert "Here is the PDF:" in result
    assert "[Document: application/pdf]" in result


def test_request_has_images_in_tool_result():
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="call_1",
                        content=[
                            TextBlock(text="Result:"),
                            ImageBlock(
                                source={"type": "base64", "media_type": "image/png", "data": "xyz"}
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    assert request_has_images(req) is True


# ---------------------------------------------------------------------------
# Response translation tests
# ---------------------------------------------------------------------------


def test_openai_to_anthropic_basic_text():
    data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello there!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    resp = openai_to_anthropic(data, "claude-sonnet-4-6")
    assert resp.id == "chatcmpl-123"
    assert resp.model == "claude-sonnet-4-6"
    assert len(resp.content) == 1
    assert resp.content[0].type == "text"
    assert resp.content[0].text == "Hello there!"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5


def test_openai_to_anthropic_with_reasoning():
    data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "deepseek-reasoner",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "42",
                    "reasoning_content": "Let me calculate...",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    resp = openai_to_anthropic(data, "claude-sonnet-4-6")
    assert len(resp.content) == 2
    assert resp.content[0].type == "thinking"
    assert resp.content[0].thinking == "Let me calculate..."
    assert resp.content[0].signature == ""
    assert resp.content[1].type == "text"
    assert resp.content[1].text == "42"


def test_openai_to_anthropic_with_tool_calls():
    data = {
        "id": "chatcmpl-123",
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
                            "function": {"name": "get_weather", "arguments": '{"location": "NYC"}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    resp = openai_to_anthropic(data, "claude-sonnet-4-6")
    assert len(resp.content) == 1
    assert resp.content[0].type == "tool_use"
    assert resp.content[0].id == "call_1"
    assert resp.content[0].name == "get_weather"
    assert resp.content[0].input == {"location": "NYC"}
    assert resp.stop_reason == "tool_use"


def test_openai_to_anthropic_usage_with_cache():
    # DeepSeek style cache
    data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
            "prompt_cache_hit_tokens": 50,
            "prompt_cache_miss_tokens": 50,
        },
    }
    resp = openai_to_anthropic(data, "claude-sonnet-4-6")
    assert resp.usage.cache_read_input_tokens == 50

    # Kimi style cache
    data["usage"] = {
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "total_tokens": 110,
        "cached_tokens": 60,
    }
    resp = openai_to_anthropic(data, "claude-opus-4-6")
    assert resp.usage.cache_read_input_tokens == 60

    # MiMo style cache (nested in prompt_tokens_details)
    data["usage"] = {
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "total_tokens": 110,
        "prompt_tokens_details": {"cached_tokens": 70},
    }
    resp = openai_to_anthropic(data, "mimo-v2.5-pro")
    assert resp.usage.cache_read_input_tokens == 70


def test_openai_to_anthropic_finish_reason_mapping():
    for openai_reason, anthropic_reason in [
        ("stop", "end_turn"),
        ("length", "max_tokens"),
        ("tool_calls", "tool_use"),
        ("content_filter", "max_tokens"),
    ]:
        data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "deepseek-chat",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hi"},
                    "finish_reason": openai_reason,
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        resp = openai_to_anthropic(data, "claude-sonnet-4-6")
        assert resp.stop_reason == anthropic_reason


# ---------------------------------------------------------------------------
# Tool result → OpenAI tool role message tests
# ---------------------------------------------------------------------------


def test_anthropic_to_openai_tool_result_becomes_tool_role_message():
    """ToolResultBlock in a user message must become a 'tool' role message."""
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[
            Message(
                role="assistant",
                content=[
                    TextBlock(text="I'll read that for you."),
                    ToolUseBlock(
                        id="call_abc123",
                        name="Read",
                        input={"file_path": "/tmp/foo.py"},
                    ),
                ],
            ),
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="call_abc123",
                        content="print('hello')",
                        is_error=False,
                    ),
                ],
            ),
        ],
        max_tokens=100,
    )
    openai_req = anthropic_to_openai(req, "kimi")

    # Should be: assistant with tool_calls, then tool message, no trailing user
    assert len(openai_req.messages) == 2
    assert openai_req.messages[0]["role"] == "assistant"
    assert openai_req.messages[0]["tool_calls"] == [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "Read",
                "arguments": json.dumps({"file_path": "/tmp/foo.py"}),
            },
        }
    ]
    assert openai_req.messages[1]["role"] == "tool"
    assert openai_req.messages[1]["tool_call_id"] == "call_abc123"
    assert openai_req.messages[1]["content"] == "print('hello')"


def test_anthropic_to_openai_tool_result_with_text_interleaved():
    """User message with tool_result + trailing text becomes tool + user messages."""
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[
            Message(
                role="assistant",
                content=[
                    ToolUseBlock(
                        id="call_def456",
                        name="Bash",
                        input={"command": "ls"},
                    ),
                ],
            ),
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="call_def456",
                        content="file.txt\nfile2.txt",
                        is_error=False,
                    ),
                    TextBlock(text="Now summarize these files."),
                ],
            ),
        ],
        max_tokens=100,
    )
    openai_req = anthropic_to_openai(req, "kimi")

    # Ordering: assistant → tool → user
    assert len(openai_req.messages) == 3
    assert openai_req.messages[0]["role"] == "assistant"
    assert openai_req.messages[1]["role"] == "tool"
    assert openai_req.messages[1]["tool_call_id"] == "call_def456"
    assert openai_req.messages[2]["role"] == "user"
    assert openai_req.messages[2]["content"] == "Now summarize these files."


def test_anthropic_to_openai_tool_result_error_flag():
    """ToolResultBlock with is_error=True prefixes content with [Error]."""
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[
            Message(
                role="assistant",
                content=[
                    ToolUseBlock(
                        id="call_err789",
                        name="Bash",
                        input={"command": "rm /"},
                    ),
                ],
            ),
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="call_err789",
                        content="Permission denied",
                        is_error=True,
                    ),
                ],
            ),
        ],
        max_tokens=100,
    )
    openai_req = anthropic_to_openai(req, "kimi")

    assert openai_req.messages[1]["role"] == "tool"
    assert openai_req.messages[1]["content"] == "[Error] Permission denied"


# ---------------------------------------------------------------------------
# DeepSeek thinking/effort passthrough tests
# ---------------------------------------------------------------------------


def test_deepseek_thinking_enabled():
    """Anthropic thinking:enabled → DeepSeek thinking: {type: enabled}."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking == {"type": "enabled"}
    assert result.reasoning_effort is None


def test_deepseek_thinking_adaptive():
    """Anthropic thinking:adaptive → DeepSeek thinking: {type: enabled}."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "adaptive"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking == {"type": "enabled"}


def test_deepseek_thinking_disabled():
    """Anthropic thinking:disabled → DeepSeek thinking: {type: disabled}."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "disabled"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking == {"type": "disabled"}


def test_deepseek_no_thinking_param():
    """No thinking param → nothing set (let DeepSeek default)."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking is None
    assert result.reasoning_effort is None


def test_deepseek_effort_passthrough():
    """output_config.effort is passed through as reasoning_effort.

    When effort is set without explicit thinking, the bridge sets
    thinking=enabled automatically — DeepSeek requires it when
    reasoning_effort is present.
    """
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        output_config={"effort": "max"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.reasoning_effort == "max"
    assert result.thinking == {"type": "enabled"}


def test_deepseek_thinking_and_effort_combined():
    """Both thinking:adaptive + effort:max produce both fields."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "adaptive"},
        output_config={"effort": "max"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking == {"type": "enabled"}
    assert result.reasoning_effort == "max"


def test_deepseek_effort_low_passthrough():
    """low effort is passed through; DeepSeek aliases it server-side."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        output_config={"effort": "low"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.reasoning_effort == "low"
    assert result.thinking == {"type": "enabled"}


def test_deepseek_effort_high_without_thinking():
    """effort=high without explicit thinking → both fields set.

    This is the exact scenario when Claude Code sends effort="high"
    without a thinking block. The bridge must auto-add thinking=enabled
    or DeepSeek hangs.
    """
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        output_config={"effort": "high"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.reasoning_effort == "high"
    assert result.thinking == {"type": "enabled"}


def test_deepseek_effort_with_disabled_thinking():
    """effort set with explicit thinking=disabled → respects disabled.

    Contradictory inputs, but explicit disable wins — don't silently
    re-enable thinking.
    """
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "disabled"},
        output_config={"effort": "high"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking == {"type": "disabled"}
    assert result.reasoning_effort == "high"


def test_kimi_ignores_thinking():
    """Kimi backend never receives thinking or reasoning_effort fields."""
    req = MessagesRequest(
        model="claude-opus-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled"},
        output_config={"effort": "max"},
    )
    result = anthropic_to_openai(req, "kimi")
    assert result.thinking is None
    assert result.reasoning_effort is None


def test_deepseek_thinking_unknown_type_ignored():
    """Unknown thinking type is not forwarded."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "unknown_value"},
    )
    result = anthropic_to_openai(req, "deepseek")
    assert result.thinking is None


def test_fireworks_thinking_enabled():
    """Fireworks uses Anthropic-compatible thinking object with budget_tokens."""
    req = MessagesRequest(
        model="fireworks-kimi-k2p6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled"},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.thinking == {"type": "enabled"}
    assert result.enable_thinking is None
    assert result.thinking_budget is None


def test_fireworks_thinking_with_budget():
    """Fireworks passes budget_tokens through in thinking object."""
    req = MessagesRequest(
        model="fireworks-kimi-k2p6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled", "budget_tokens": 8192},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.thinking == {"type": "enabled", "budget_tokens": 8192}


def test_fireworks_thinking_disabled():
    """Fireworks thinking=disabled sends {type: disabled} for Kimi."""
    req = MessagesRequest(
        model="fireworks-kimi-k2p6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "disabled"},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.thinking == {"type": "disabled"}


def test_fireworks_effort_as_reasoning_effort():
    """Fireworks uses reasoning_effort when no thinking type is set."""
    req = MessagesRequest(
        model="fireworks-kimi-k2p6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        output_config={"effort": "high"},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.reasoning_effort == "high"
    assert result.thinking is None


def test_fireworks_clamps_effort_xhigh_and_max_to_high():
    """Fireworks MiniMax M2 only accepts low/medium/high; clamp xhigh/max."""
    for effort_in, expected in [("xhigh", "high"), ("max", "high")]:
        req = MessagesRequest(
            model="fireworks-minimax-m2p7",
            messages=[Message(role="user", content="Hello")],
            max_tokens=100,
            output_config={"effort": effort_in},
        )
        result = anthropic_to_openai(req, "fireworks")
        assert result.reasoning_effort == expected, f"{effort_in} → {expected}"
        assert result.thinking is None


def test_minimax_budget_converts_to_effort():
    """MiniMax M2 maps budget_tokens to reasoning_effort string."""
    cases = [
        (2048, "low"),
        (4096, "low"),
        (5000, "medium"),
        (8192, "medium"),
        (12000, "high"),
        (16384, "high"),
        (32000, "high"),
    ]
    for budget, expected_effort in cases:
        req = MessagesRequest(
            model="fireworks-minimax-m2p7",
            messages=[Message(role="user", content="Hello")],
            max_tokens=100,
            thinking={"type": "enabled", "budget_tokens": budget},
        )
        result = anthropic_to_openai(req, "fireworks")
        assert result.reasoning_effort == expected_effort, (
            f"budget {budget} → {expected_effort}, got {result.reasoning_effort}"
        )
        assert result.thinking is None


def test_minimax_prefers_output_config_over_budget():
    """MiniMax M2 prefers output_config.effort over budget_tokens mapping."""
    req = MessagesRequest(
        model="fireworks-minimax-m2p7",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled", "budget_tokens": 32000},
        output_config={"effort": "low"},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.reasoning_effort == "low"
    assert result.thinking is None


def test_minimax_thinking_disabled_sends_nothing():
    """MiniMax M2 with disabled thinking sends no thinking or effort."""
    req = MessagesRequest(
        model="fireworks-minimax-m2p7",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "disabled"},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.thinking is None
    assert result.reasoning_effort is None


def test_minimax_no_thinking_no_output_config_sends_nothing():
    """MiniMax M2 with no thinking and no output_config sends nothing."""
    req = MessagesRequest(
        model="fireworks-minimax-m2p7",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.thinking is None
    assert result.reasoning_effort is None


def test_fireworks_ignores_siliconflow_params():
    """Fireworks backend never receives enable_thinking or thinking_budget."""
    req = MessagesRequest(
        model="fireworks-kimi-k2p6",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled"},
    )
    result = anthropic_to_openai(req, "fireworks")
    assert result.enable_thinking is None
    assert result.thinking_budget is None


# ── MiMo thinking/effort tests ──────────────────────────────────────


def test_mimo_thinking_enabled():
    """MiMo maps thinking enabled to thinking {type: enabled}."""
    req = MessagesRequest(
        model="mimo-v2.5-pro",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled"},
    )
    result = anthropic_to_openai(req, "mimo")
    assert result.thinking == {"type": "enabled"}
    assert result.reasoning_effort is None


def test_mimo_thinking_adaptive():
    """MiMo maps thinking adaptive to thinking {type: enabled}."""
    req = MessagesRequest(
        model="mimo-v2.5-pro",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "adaptive"},
    )
    result = anthropic_to_openai(req, "mimo")
    assert result.thinking == {"type": "enabled"}


def test_mimo_thinking_disabled():
    """MiMo maps thinking disabled to thinking {type: disabled}."""
    req = MessagesRequest(
        model="mimo-v2.5-pro",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "disabled"},
    )
    result = anthropic_to_openai(req, "mimo")
    assert result.thinking == {"type": "disabled"}
    assert result.reasoning_effort is None


def test_mimo_thinking_with_budget():
    """MiMo passes through budget_tokens in thinking object."""
    req = MessagesRequest(
        model="mimo-v2.5-pro",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled", "budget_tokens": 4096},
    )
    result = anthropic_to_openai(req, "mimo")
    assert result.thinking == {"type": "enabled", "budget_tokens": 4096}


def test_mimo_effort_low_medium_high():
    """MiMo passes through low/medium/high effort values."""
    for effort in ("low", "medium", "high"):
        req = MessagesRequest(
            model="mimo-v2.5-pro",
            messages=[Message(role="user", content="Hello")],
            max_tokens=100,
            output_config={"effort": effort},
        )
        result = anthropic_to_openai(req, "mimo")
        assert result.reasoning_effort == effort
        assert result.thinking is None


def test_mimo_effort_xhigh_max_clamped_to_high():
    """MiMo clamps xhigh and max to high (only supports low/medium/high)."""
    for effort in ("xhigh", "max"):
        req = MessagesRequest(
            model="mimo-v2.5-pro",
            messages=[Message(role="user", content="Hello")],
            max_tokens=100,
            output_config={"effort": effort},
        )
        result = anthropic_to_openai(req, "mimo")
        assert result.reasoning_effort == "high"


def test_mimo_no_thinking_param():
    """MiMo with no thinking sends nothing."""
    req = MessagesRequest(
        model="mimo-v2.5-pro",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "mimo")
    assert result.thinking is None
    assert result.reasoning_effort is None


def test_mimo_thinking_and_effort_combined():
    """MiMo sends both thinking object and reasoning_effort when both specified."""
    req = MessagesRequest(
        model="mimo-v2.5-pro",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        thinking={"type": "enabled", "budget_tokens": 2048},
        output_config={"effort": "high"},
    )
    result = anthropic_to_openai(req, "mimo")
    assert result.thinking == {"type": "enabled", "budget_tokens": 2048}
    assert result.reasoning_effort == "high"


# ── cache_control forwarding tests ──────────────────────────────────


def test_cache_control_forwarded_on_text_block():
    """cache_control on TextBlock is preserved in OpenAI translation."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    TextBlock(type="text", text="my question", cache_control={"type": "ephemeral"})
                ],
            ),
        ],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "deepseek")
    # With images absent, content collapses to string — cache_control lost
    # (this path is documented; mixed-content blocks preserve it)
    assert isinstance(result.messages[-1]["content"], str)


def test_cache_control_forwarded_on_mixed_content():
    """cache_control on TextBlock is preserved when content is mixed (has images)."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    TextBlock(
                        type="text", text="describe this", cache_control={"type": "ephemeral"}
                    ),
                    ImageBlock(
                        type="image",
                        source={"type": "base64", "media_type": "image/png", "data": "aaaa"},
                    ),
                ],
            ),
        ],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "deepseek")
    content = result.messages[-1]["content"]
    assert isinstance(content, list)
    text_part = next(p for p in content if p["type"] == "text")
    assert text_part["cache_control"] == {"type": "ephemeral"}


def test_cache_control_forwarded_on_tool_result():
    """cache_control on ToolResultBlock is preserved in tool message."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="call_123",
                        content="result text",
                        cache_control={"type": "ephemeral"},
                    )
                ],
            ),
        ],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "deepseek")
    tool_msg = result.messages[0]
    assert tool_msg["role"] == "tool"
    assert tool_msg["cache_control"] == {"type": "ephemeral"}


def test_cache_control_forwarded_on_system_prompt():
    """System prompt is collapsed to string (preserves tokenization for caching).
    cache_control on individual blocks is lost, but backends use auto-detection."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="hi")],
        max_tokens=100,
        system=[
            TextBlock(type="text", text="cached system", cache_control={"type": "ephemeral"}),
        ],
    )
    result = anthropic_to_openai(req, "deepseek")
    sys_msg = result.messages[0]
    assert isinstance(sys_msg["content"], str)
    assert sys_msg["content"] == "cached system"


def test_cache_control_disabled_when_flag_off():
    """When forward_cache_control=False, cache_control is stripped."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="call_123",
                        content="result",
                        cache_control={"type": "ephemeral"},
                    )
                ],
            ),
        ],
        max_tokens=100,
    )
    result = anthropic_to_openai(req, "deepseek", forward_cache_control=False)
    tool_msg = result.messages[0]
    assert "cache_control" not in tool_msg
