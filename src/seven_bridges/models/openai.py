"""OpenAI Chat Completions API request/response schemas.

https://platform.openai.com/docs/api-reference/chat
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: str


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str | list[dict[str, Any]]


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    reasoning_content: str | None = None


class ToolMessage(BaseModel):
    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str


ChatMessage = SystemMessage | UserMessage | AssistantMessage | ToolMessage


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class FunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None
    strict: bool | None = None


class ChatCompletionTool(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionDefinition


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class StreamOptions(BaseModel):
    include_usage: bool | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    max_tokens: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool | None = False
    stop: str | list[str] | None = None
    tools: list[ChatCompletionTool] | None = None
    tool_choice: Literal["none", "auto", "required"] | dict[str, Any] | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    user: str | None = None
    stream_options: StreamOptions | None = None
    prompt_cache_key: str | None = None
    reasoning_effort: str | None = None
    thinking: dict[str, Any] | None = None
    enable_thinking: bool | None = None
    thinking_budget: int | None = None


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class CompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    cached_tokens: int | None = None  # Kimi uses this field


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class Choice(BaseModel):
    index: int = 0
    message: AssistantMessage
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: CompletionUsage | None = None


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


class DeltaMessage(BaseModel):
    role: Literal["assistant"] | None = None
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class StreamingChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamingChoice]
    usage: CompletionUsage | None = None
