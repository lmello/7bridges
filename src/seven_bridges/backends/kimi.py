"""Kimi bridge — translates Anthropic Messages API to Kimi Code API."""

import json
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

    @staticmethod
    def _normalize_usage(usage: dict[str, Any]) -> dict[str, Any]:
        """Convert Kimi-format usage to the OpenAI-style keys expected by
        _log_usage_from_context and the usage log module.

        Kimi returns ``cached_tokens`` but not ``prompt_cache_hit_tokens``
        or ``prompt_cache_miss_tokens``. We compute the missing fields so
        the cache hit rate formula ``hit / (hit + miss)`` works correctly.
        """
        prompt_tok: int = usage.get("prompt_tokens", 0)
        completion_tok: int = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", prompt_tok + completion_tok)
        cached: int = usage.get("cached_tokens") or 0
        return {
            "prompt_tokens": prompt_tok,
            "completion_tokens": completion_tok,
            "total_tokens": total,
            "cached_tokens": cached,
            "prompt_cache_hit_tokens": cached,
            "prompt_cache_miss_tokens": max(0, prompt_tok - cached),
        }

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming request to Kimi."""
        self.start_timer()
        openai_request = anthropic_to_openai(request, self.name, self.forward_cache_control)
        openai_request.model = self.backend_model

        try:
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
                        usage=self._normalize_usage(usage),
                        stop_reason=_map_stop_reason(
                            raw.get("choices", [{}])[0].get("finish_reason")
                        ),
                    )

                return openai_to_anthropic(raw, self.model_alias)
        except httpx.RequestError as exc:
            raise BridgeError(
                message=f"Upstream connection error: {exc}",
                status_code=502,
                error_type="api_error",
            ) from exc

    async def chat_stream(self, request: MessagesRequest) -> AsyncIterator[dict[str, Any]]:
        """Send a streaming request to Kimi and yield Anthropic-format events."""
        self.start_timer()
        openai_request = anthropic_to_openai(request, self.name, self.forward_cache_control)
        openai_request.model = self.backend_model
        openai_request.stream = True
        from seven_bridges.models.openai import StreamOptions

        openai_request.stream_options = StreamOptions(include_usage=True)

        try:
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
                    self._log_error_from_context(
                        status_code=response.status_code,
                        error_type=error_type,
                        message=body.decode(),
                    )
                    raise BridgeError(
                        message=body.decode(),
                        status_code=response.status_code,
                        error_type=error_type,
                    )

                _logged_usage = False
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            usage = chunk.get("usage")
                            if usage and not _logged_usage:
                                self._log_usage_from_context(
                                    response_id=chunk.get("id"),
                                    usage=self._normalize_usage(usage),
                                    stop_reason=None,
                                )
                                _logged_usage = True
                        except json.JSONDecodeError:
                            import logging

                            logger = logging.getLogger(__name__)
                            logger.warning("Failed to parse stream chunk: %r", data)
                        yield {"type": "raw", "data": data}
        except httpx.RequestError as exc:
            raise BridgeError(
                message=f"Upstream stream connection error: {exc}",
                status_code=502,
                error_type="api_error",
            ) from exc


def _map_stop_reason(finish_reason: str | None) -> str | None:
    """Map OpenAI finish_reason to Anthropic stop_reason for usage logging."""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "max_tokens",
    }
    return mapping.get(finish_reason or "")
