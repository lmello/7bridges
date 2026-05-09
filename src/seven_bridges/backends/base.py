"""Abstract base class for backend bridges."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
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

    @abstractmethod
    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        """Send a non-streaming chat request and return the translated response."""
        ...

    @abstractmethod
    def chat_stream(self, request: MessagesRequest) -> AsyncIterator[dict[str, Any]]:
        """Send a streaming chat request and yield Anthropic-format SSE events."""
        ...
