"""Abstract base class for backend bridges."""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from seven_bridges.models.anthropic import MessagesRequest, MessagesResponse


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
        self.usage_context: dict[str, Any] | None = None

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

    @abstractmethod
    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming chat request and return the translated response."""
        ...

    @abstractmethod
    def chat_stream(self, request: MessagesRequest) -> AsyncIterator[dict[str, Any]]:
        """Send a streaming chat request and yield Anthropic-format SSE events."""
        ...
