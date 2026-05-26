"""Kimi bridge — translates Anthropic Messages API to Kimi Code API."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from seven_bridges.backends.base import Bridge, BridgeError, VendorCapabilities
from seven_bridges.models.anthropic import MessagesRequest, MessagesResponse
from seven_bridges.translation.request import anthropic_to_openai
from seven_bridges.translation.response import openai_to_anthropic
from seven_bridges.usage_log import _log_usage


def _map_http_error(status_code: int) -> str:
    """Map HTTP status code to Anthropic-style error type."""
    mapping = {
        400: "invalid_request_error",
        401: "authentication_error",
        403: "permission_error",
        404: "not_found_error",
        422: "invalid_request_error",
        429: "rate_limit_error",
        500: "api_error",
        502: "api_error",
        503: "overloaded_error",
        504: "api_error",
    }
    return mapping.get(status_code, "api_error")


class KimiBridge(Bridge):
    """Bridge to Kimi Code API (OpenAI-compatible)."""

    name = "kimi"
    default_api_base = "https://api.kimi.com/coding/v1"
    capabilities = VendorCapabilities(
        supports_vision=True,
        supports_reasoning=True,
        supports_tool_calls=True,
        supports_video=True,
        max_tokens=262144,
    )

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming request to Kimi."""
        openai_request = anthropic_to_openai(request, self.name)
        openai_request.model = self.backend_model

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "claude-code/0.1.0",
                },
                json=openai_request.model_dump(exclude_none=True),
                timeout=300.0,
            )

            if response.status_code != 200:
                error_type = _map_http_error(response.status_code)
                raise BridgeError(
                    message=response.text,
                    status_code=response.status_code,
                    error_type=error_type,
                )

            raw = response.json()
            usage = raw.get("usage")
            ctx = self.usage_context
            if usage and ctx:
                _log_usage(
                    bridge_name=self.name,
                    model_alias=self.model_alias,
                    backend_model=self.backend_model,
                    response_id=raw.get("id"),
                    usage=usage,
                    stream=ctx.get("stream", False),
                    max_tokens=ctx.get("max_tokens"),
                    thinking_enabled=ctx.get("thinking_enabled"),
                    thinking_budget=ctx.get("thinking_budget"),
                    tool_count=ctx.get("tool_count", 0),
                    tool_names=ctx.get("tool_names", []),
                    message_count=ctx.get("message_count", 0),
                    has_images=ctx.get("has_images", False),
                    has_video=ctx.get("has_video", False),
                    temperature=ctx.get("temperature"),
                    top_p=ctx.get("top_p"),
                    session_id=ctx.get("session_id"),
                    client_app=ctx.get("client_app"),
                    user_agent=ctx.get("user_agent"),
                    api_key_prefix=ctx.get("api_key_prefix"),
                    stop_reason=_map_stop_reason(raw.get("choices", [{}])[0].get("finish_reason")),
                    client_metadata=ctx.get("client_metadata"),
                )

            return openai_to_anthropic(raw, self.model_alias)

    async def chat_stream(self, request: MessagesRequest) -> AsyncIterator[dict[str, Any]]:
        """Send a streaming request to Kimi and yield Anthropic-format events."""
        openai_request = anthropic_to_openai(request, self.name)
        openai_request.model = self.backend_model
        openai_request.stream = True
        from seven_bridges.models.openai import StreamOptions

        openai_request.stream_options = StreamOptions(include_usage=True)

        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "User-Agent": "claude-code/0.1.0",
                },
                json=openai_request.model_dump(exclude_none=True),
                timeout=300.0,
            ) as response,
        ):
            if response.status_code != 200:
                body = await response.aread()
                error_type = _map_http_error(response.status_code)
                raise BridgeError(
                    message=body.decode(),
                    status_code=response.status_code,
                    error_type=error_type,
                )

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    # Detect usage-only chunks (from include_usage=True)
                    try:
                        chunk = json.loads(data)
                        choices = chunk.get("choices", [])
                        usage = chunk.get("usage")
                        if not choices and usage:
                            ctx = self.usage_context
                            if ctx:
                                _log_usage(
                                    bridge_name=self.name,
                                    model_alias=self.model_alias,
                                    backend_model=self.backend_model,
                                    response_id=chunk.get("id"),
                                    usage=usage,
                                    stream=ctx.get("stream", True),
                                    max_tokens=ctx.get("max_tokens"),
                                    thinking_enabled=ctx.get("thinking_enabled"),
                                    thinking_budget=ctx.get("thinking_budget"),
                                    tool_count=ctx.get("tool_count", 0),
                                    tool_names=ctx.get("tool_names", []),
                                    message_count=ctx.get("message_count", 0),
                                    has_images=ctx.get("has_images", False),
                                    has_video=ctx.get("has_video", False),
                                    temperature=ctx.get("temperature"),
                                    top_p=ctx.get("top_p"),
                                    session_id=ctx.get("session_id"),
                                    client_app=ctx.get("client_app"),
                                    user_agent=ctx.get("user_agent"),
                                    api_key_prefix=ctx.get("api_key_prefix"),
                                    stop_reason=None,
                                    client_metadata=ctx.get("client_metadata"),
                                )
                    except json.JSONDecodeError:
                        pass
                    yield {"type": "raw", "data": data}


def _map_stop_reason(finish_reason: str | None) -> str | None:
    """Map OpenAI finish_reason to Anthropic stop_reason for usage logging."""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "max_tokens",
    }
    return mapping.get(finish_reason or "")
