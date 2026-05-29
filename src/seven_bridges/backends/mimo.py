"""Xiaomi MiMo bridge — dual-mode backend.

- Anthropic passthrough (default): proxies directly to MiMo's native
  /anthropic/v1/messages endpoint.  Cache_control breakpoints work natively,
  reasoning is returned as thinking blocks, and streaming preserves all
  Anthropic SSE events.  No OpenAI translation overhead.

- OpenAI-compatible (legacy): translates via the standard OpenAI path for
  the /v1/chat/completions endpoint.  Prompt caching uses prompt_cache_key.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from seven_bridges.backends.base import Bridge, BridgeError, VendorCapabilities
from seven_bridges.models.anthropic import MessagesRequest, MessagesResponse


def _map_http_error(status_code: int) -> str:
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


class MiMoBridge(Bridge):
    """Anthropic-native passthrough to MiMo's /anthropic/v1/messages.

    Requests and responses are passed through with no OpenAI translation.
    Claude Code's cache_control breakpoints go directly to MiMo, so prompt
    caching works out of the box.
    """

    name = "mimo"
    default_api_base = "https://token-plan-sgp.xiaomimimo.com/anthropic/v1"
    is_passthrough = True
    capabilities = VendorCapabilities(
        supports_vision=True,
        supports_reasoning=True,
        supports_tool_calls=True,
        supports_video=False,
        max_tokens=32768,
    )

    def _headers(self) -> dict[str, str]:
        """Build request headers, forwarding Anthropic beta features if present."""
        h = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        if self._anthropic_beta:
            h["anthropic-beta"] = self._anthropic_beta
        return h

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        self.start_timer()
        body = request.model_dump(exclude_none=True)
        body["model"] = self.backend_model

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/messages",
                headers=self._headers(),
                json=body,
                timeout=300.0,
            )

            if response.status_code != 200:
                error_type = _map_http_error(response.status_code)
                self._log_error_from_context(
                    status_code=response.status_code,
                    error_type=error_type,
                    message=response.text,
                )
                raise BridgeError(
                    message=response.text,
                    status_code=response.status_code,
                    error_type=error_type,
                )

            raw = response.json()
            usage = raw.get("usage")
            if usage:
                self._log_usage_from_context(
                    response_id=raw.get("id"),
                    usage=usage,
                    stop_reason=raw.get("stop_reason"),
                )

            return MessagesResponse.model_validate(raw)

    async def chat_stream(self, request: MessagesRequest) -> AsyncIterator[str]:
        self.start_timer()
        body = request.model_dump(exclude_none=True)
        body["model"] = self.backend_model
        body["stream"] = True

        headers = self._headers()
        headers["Accept"] = "text/event-stream"

        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST",
                f"{self.api_base}/messages",
                headers=headers,
                json=body,
                timeout=300.0,
            ) as response,
        ):
            if response.status_code != 200:
                error_body = await response.aread()
                error_type = _map_http_error(response.status_code)
                self._log_error_from_context(
                    status_code=response.status_code,
                    error_type=error_type,
                    message=error_body.decode(),
                )
                raise BridgeError(
                    message=error_body.decode(),
                    status_code=response.status_code,
                    error_type=error_type,
                )

            usage_data: dict[str, Any] = {}
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    msg_type = chunk.get("type", "")
                    if msg_type == "message_stop":
                        self._log_usage_from_context(
                            response_id=chunk.get("id"),
                            usage=usage_data,
                            stop_reason=None,
                        )
                    elif "usage" in chunk:
                        usage_data = chunk.get("usage") or usage_data

                yield line + "\n"
