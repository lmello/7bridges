"""DeepSeek bridge — translates Anthropic Messages API to DeepSeek's OpenAI API."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from seven_bridges.backends.base import Bridge, BridgeError
from seven_bridges.models.anthropic import MessagesRequest, MessagesResponse
from seven_bridges.translation.request import anthropic_to_openai
from seven_bridges.translation.response import openai_to_anthropic


class DeepSeekBridge(Bridge):
    """Bridge to DeepSeek's OpenAI-compatible API."""

    name = "deepseek"
    default_api_base = "https://api.deepseek.com/beta"

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming request to DeepSeek."""
        openai_request = anthropic_to_openai(request, self.name)

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
                raise BridgeError(
                    message=response.text,
                    status_code=response.status_code,
                    error_type="deepseek_error",
                )

            return openai_to_anthropic(response.json(), request.model)

    async def chat_stream(self, request: MessagesRequest) -> AsyncIterator[dict[str, Any]]:
        """Send a streaming request to DeepSeek and yield Anthropic-format events."""
        openai_request = anthropic_to_openai(request, self.name)
        openai_request.stream = True

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
                raise BridgeError(
                    message=body.decode(),
                    status_code=response.status_code,
                    error_type="deepseek_error",
                )

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    # TODO: Translate OpenAI SSE chunk to Anthropic event
                    yield {"type": "raw", "data": data}
