"""MiniMax bridge — Anthropic-native passthrough.

Proxies directly to MiniMax's /anthropic/v1/messages endpoint.
Cache_control breakpoints work natively, thinking blocks pass through
unchanged, and streaming preserves all Anthropic SSE events.
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


class MiniMaxBridge(Bridge):
    """Anthropic-native passthrough to MiniMax's /anthropic/v1/messages.

    Requests and responses are passed through with no OpenAI translation.
    Claude Code's cache_control breakpoints go directly to MiniMax, so
    explicit prompt caching works out of the box.
    """

    name = "minimax"
    default_api_base = "https://api.minimax.io/anthropic/v1"
    is_passthrough = True
    capabilities = VendorCapabilities(
        supports_vision=True,
        supports_reasoning=True,
        supports_tool_calls=True,
        supports_video=False,
        max_tokens=204800,
    )

    def _headers(self) -> dict[str, str]:
        """Build request headers, forwarding Anthropic beta features if present."""
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self._anthropic_beta:
            h["anthropic-beta"] = self._anthropic_beta
        return h

    @staticmethod
    def _normalize_usage(anthropic_usage: dict[str, Any]) -> dict[str, Any]:
        """Convert Anthropic-format usage to OpenAI-style keys.

        MiniMax returns explicit cache fields:
          - cache_read_input_tokens  (hits)
          - cache_creation_input_tokens  (writes)
          - input_tokens  (uncached portion after last breakpoint)
          - output_tokens

        We map cache_read → hit, (cache_creation + input_tokens) → miss so
        the cache hit rate formula produces the correct percentage.
        """
        input_tok: int = anthropic_usage.get("input_tokens", 0)
        output_tok: int = anthropic_usage.get("output_tokens", 0)
        cache_read: int = anthropic_usage.get("cache_read_input_tokens") or 0
        cache_creation: int = anthropic_usage.get("cache_creation_input_tokens") or 0
        total_input = input_tok + cache_read + cache_creation
        return {
            "prompt_tokens": total_input,
            "completion_tokens": output_tok,
            "total_tokens": total_input + output_tok,
            "cached_tokens": cache_read,
            "prompt_cache_hit_tokens": cache_read,
            "prompt_cache_miss_tokens": cache_creation + input_tok,
        }

    def _inject_cache_control(self, body: dict[str, Any]) -> None:
        """Inject cache_control: ephemeral on static content to maximize prefix caching.

        Per MiniMax docs, cache_control markers should be placed on system prompts
        and tool definitions — the most static, largest portions of the prompt.
        We mark the last block of system (if any) and the last tool (if any)
        with cache_control: ephemeral. MiniMax ignores duplicate markers when
        the content hasn't changed, so session resumption is safe without
        tracking state.
        """
        if not self.explicit_cache:
            return

        # Mark last system block
        system = body.get("system")
        if isinstance(system, list) and system:
            for block in reversed(system):
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    block["cache_control"] = {"type": "ephemeral"}
                    break

        # Mark last tool
        tools = body.get("tools")
        if isinstance(tools, list) and tools:
            for block in reversed(tools):
                if isinstance(block, dict) and block.get("name"):
                    block["cache_control"] = {"type": "ephemeral"}
                    break

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming request to MiniMax."""
        self.start_timer()
        body = request.model_dump(exclude_none=True)
        body["model"] = self.backend_model
        self._inject_cache_control(body)

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
            # MiniMax may return content: null on truncated/max-tokens responses.
            # Normalize to an empty list so Pydantic validation succeeds.
            if raw.get("content") is None:
                raw["content"] = []
            usage = raw.get("usage")
            if usage:
                self._log_usage_from_context(
                    response_id=raw.get("id"),
                    usage=self._normalize_usage(usage),
                    stop_reason=raw.get("stop_reason"),
                )

            return MessagesResponse.model_validate(raw)

    async def chat_stream(self, request: MessagesRequest) -> AsyncIterator[str]:
        """Send a streaming request to MiniMax and yield Anthropic SSE lines."""
        self.start_timer()
        body = request.model_dump(exclude_none=True)
        body["model"] = self.backend_model
        body["stream"] = True
        self._inject_cache_control(body)

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
                            usage=self._normalize_usage(usage_data),
                            stop_reason=None,
                        )
                    elif "usage" in chunk and chunk["usage"]:
                        # Always overwrite — message_start has zeroed usage;
                        # message_delta has the real data and arrives later.
                        usage_data = chunk["usage"]

                yield line + "\n"
