"""Unit tests for Anthropic ↔ OpenAI translation layer."""

import json

from seven_bridges.models.anthropic import (
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
