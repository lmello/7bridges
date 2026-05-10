"""DeepSeek bridge — translates Anthropic Messages API to DeepSeek's OpenAI API."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from seven_bridges.backends.base import Bridge, BridgeError, VendorCapabilities
from seven_bridges.models.anthropic import MessagesRequest, MessagesResponse
from seven_bridges.translation.request import anthropic_to_openai
from seven_bridges.translation.response import openai_to_anthropic


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


class DeepSeekBridge(Bridge):
    """Bridge to DeepSeek's OpenAI-compatible API."""

    name = "deepseek"
    default_api_base = "https://api.deepseek.com/beta"
    capabilities = VendorCapabilities(
        supports_vision=False,
        supports_reasoning=True,
        supports_tool_calls=True,
        supports_video=False,
        max_tokens=8192,
    )

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming request to DeepSeek."""
        openai_request = anthropic_to_openai(request, self.name)
        openai_request.model = self.backend_model

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
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

            return openai_to_anthropic(response.json(), self.model_alias)

    async def chat_stream(self, request: MessagesRequest) -> AsyncIterator[dict[str, Any]]:
        """Send a streaming request to DeepSeek and yield Anthropic-format events."""
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
                    yield {"type": "raw", "data": data}
