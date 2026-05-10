"""Anthropic Messages API request/response schemas.

https://docs.anthropic.com/en/api/messages
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Anthropic cryptographically signs thinking blocks for multi-turn continuity.
# Upstream vendors (Kimi, DeepSeek, etc.) do not provide signatures.
# Claude Code requires signature to be a non-null string, so we use an empty
# string as a placeholder. This is a vendor limitation, not a bridge bug.
_SIGNATURE_PLACEHOLDER: str = ""

# ---------------------------------------------------------------------------
# Content blocks
# ---------------------------------------------------------------------------


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ThinkingBlock(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str
    signature: str = _SIGNATURE_PLACEHOLDER


class RedactedThinkingBlock(BaseModel):
    type: Literal["redacted_thinking"] = "redacted_thinking"
    data: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    source: dict[str, Any]


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str | list[TextBlock | ImageBlock] | None = None
    is_error: bool | None = None


ContentBlock = (
    TextBlock | ThinkingBlock | RedactedThinkingBlock | ImageBlock | ToolUseBlock | ToolResultBlock
)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[ContentBlock]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class ToolInputSchema(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, Any] | None = None
    required: list[str] | None = None


class Tool(BaseModel):
    name: str
    description: str | None = None
    input_schema: ToolInputSchema


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class MessagesRequest(BaseModel):
    model: str
    messages: list[Message]
    max_tokens: int = Field(default=4096)
    system: str | list[TextBlock] | None = None
    metadata: dict[str, Any] | None = None
    stop_sequences: list[str] | None = None
    stream: bool | None = False
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0)
    tool_choice: Literal["auto", "any", "none"] | dict[str, Any] | None = None
    tools: list[Tool] | None = None
    thinking: dict[str, Any] | None = None  # Anthropic-native; stripped by bridges


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class MessagesResponse(BaseModel):
    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[ContentBlock]
    stop_reason: Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"] | None = None
    stop_sequence: str | None = None
    usage: Usage


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


class ContentBlockDelta(BaseModel):
    type: Literal["text_delta", "thinking_delta", "signature_delta", "input_json_delta"]
    text: str | None = None
    thinking: str | None = None
    signature: str | None = None
    partial_json: str | None = None


class ContentBlockStart(BaseModel):
    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: ContentBlock


class ContentBlockDeltaEvent(BaseModel):
    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: ContentBlockDelta


class ContentBlockStopEvent(BaseModel):
    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class MessageStartEvent(BaseModel):
    type: Literal["message_start"] = "message_start"
    message: MessagesResponse


class MessageDeltaEvent(BaseModel):
    type: Literal["message_delta"] = "message_delta"
    delta: dict[str, Any]
    usage: Usage | None = None


class MessageStopEvent(BaseModel):
    type: Literal["message_stop"] = "message_stop"
