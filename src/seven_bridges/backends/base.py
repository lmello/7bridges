"""Abstract base class for backend bridges."""

import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from seven_bridges.error_log import log_error
from seven_bridges.models.anthropic import MessagesRequest, MessagesResponse
from seven_bridges.usage_log import _compute_cache_hit_rate, _compute_cost, _log_usage


class BridgeError(Exception):
    """Error raised by a bridge during request/response handling."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_type: str = "api_error",
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(message)


@dataclass(frozen=True)
class VendorCapabilities:
    """Capabilities of an upstream vendor."""

    supports_vision: bool = False
    supports_reasoning: bool = False
    supports_tool_calls: bool = True
    supports_video: bool = False
    max_tokens: int = 8192


class Bridge(ABC):
    """Abstract base class for translating between Anthropic and a native backend."""

    name: str = ""
    default_api_base: str = ""
    is_passthrough: bool = False  # True if the bridge proxies Anthropic natively (no translation)
    capabilities: VendorCapabilities = VendorCapabilities()

    def __init__(
        self,
        api_key: str,
        api_base: str | None = None,
        model_alias: str = "",
        backend_model: str = "",
    ):
        self.api_key = api_key
        self.api_base = api_base or self.default_api_base
        self.model_alias = model_alias
        self.backend_model = backend_model
        self._debug_log_path: str | None = None
        self._anthropic_beta: str | None = None
        self.usage_context: dict[str, Any] | None = None
        self._request_start_time: float | None = None

    def _log_outgoing(self, outgoing: dict[str, Any]) -> None:
        """Log the translated outgoing request to the debug JSONL file."""
        if not self._debug_log_path:
            return
        entry = {
            "type": "outgoing_request",
            "timestamp": datetime.now(UTC).isoformat(),
            "backend": self.name,
            "model": outgoing.get("model"),
            "stream": outgoing.get("stream"),
            "thinking": outgoing.get("thinking"),
            "reasoning_effort": outgoing.get("reasoning_effort"),
            "enable_thinking": outgoing.get("enable_thinking"),
            "thinking_budget": outgoing.get("thinking_budget"),
            "max_tokens": outgoing.get("max_tokens"),
            "tool_count": len(outgoing.get("tools", [])),
            "message_count": len(outgoing.get("messages", [])),
        }
        with open(self._debug_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def start_timer(self) -> None:
        """Record the current time as the request start time."""
        self._request_start_time = time.time()

    def stop_timer(self) -> float | None:
        """Return elapsed time in milliseconds since start_timer() was called.

        Resets the start time to None after reading.
        """
        if self._request_start_time is None:
            return None
        elapsed_ms = (time.time() - self._request_start_time) * 1000
        self._request_start_time = None
        return elapsed_ms

    def _log_usage_from_context(
        self,
        *,
        response_id: str | None,
        usage: dict[str, Any],
        stop_reason: str | None,
        status_code: int = 200,
    ) -> None:
        """Log usage data enriched with context fields and computed metrics.

        Called by backends after extracting usage from upstream response.
        Silently returns if usage_context is not set.
        """
        ctx = self.usage_context
        if not ctx:
            return
        latency_ms = self.stop_timer()
        cost = _compute_cost(usage, backend=self.name, model_alias=self.model_alias)
        cache_hit_rate = _compute_cache_hit_rate(usage)
        _log_usage(
            bridge_name=self.name,
            model_alias=self.model_alias,
            backend_model=self.backend_model,
            response_id=response_id,
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
            stop_reason=stop_reason,
            client_metadata=ctx.get("client_metadata"),
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            cache_headers_sent=None,
            cache_hit_rate=cache_hit_rate,
        )

    def _log_error_from_context(
        self,
        *,
        status_code: int,
        error_type: str,
        message: str,
    ) -> None:
        """Log an error enriched with context fields.

        Called by backends on error paths.
        Silently returns if usage_context is not set.
        """
        ctx = self.usage_context
        if not ctx:
            return
        latency_ms = self.stop_timer()
        log_error(
            bridge=self.name,
            model_alias=self.model_alias,
            backend_model=self.backend_model,
            status_code=status_code,
            error_type=error_type,
            message=message,
            latency_ms=latency_ms,
            stream=ctx.get("stream", False),
            tool_count=ctx.get("tool_count", 0),
            has_images=ctx.get("has_images", False),
            has_video=ctx.get("has_video", False),
            client_app=ctx.get("client_app"),
            session_id=ctx.get("session_id"),
            user_agent=ctx.get("user_agent"),
            api_key_prefix=ctx.get("api_key_prefix"),
        )

    @abstractmethod
    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming chat request and return the translated response."""
        ...

    @abstractmethod
    def chat_stream(self, request: MessagesRequest) -> AsyncIterator[str | dict[str, Any]]:
        """Send a streaming chat request and yield Anthropic-format SSE events.

        OpenAI-translating bridges yield ``{"type": "raw", "data": ...}`` dicts
        for the stream translator.  Passthrough bridges yield full SSE text
        lines (``"event: ...\\ndata: {...}\\n\\n"``).
        """
        ...
