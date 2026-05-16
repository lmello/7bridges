"""Ollama bridge — translates Anthropic Messages API to Ollama's native chat API."""

import json
import sys
import traceback
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal, cast

from ollama import AsyncClient, ChatResponse, Message, Tool

from seven_bridges.backends.base import Bridge, BridgeError, VendorCapabilities
from seven_bridges.models.anthropic import (
    _SIGNATURE_PLACEHOLDER,
    MessagesRequest,
    MessagesResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)


def _log_stderr(level: str, message: str, **details: Any) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "level": level,
        "bridge": "ollama",
        "msg": message,
        **details,
    }
    print(json.dumps(entry, ensure_ascii=False, default=str), file=sys.stderr)


def _map_done_reason(done_reason: str | None) -> str | None:
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "max_tokens",
    }
    return mapping.get(done_reason or "")


def _anthropic_messages_to_ollama(
    request: MessagesRequest,
) -> tuple[list[Message], str | None, list[Tool] | None]:
    """Convert Anthropic messages and tools to Ollama format.

    Returns (messages, system_prompt, tools).
    """
    messages: list[Message] = []
    system_prompt: str | None = None

    # System prompt
    if request.system:
        if isinstance(request.system, str):
            system_prompt = request.system
        else:
            system_prompt = "\n".join(
                block.text for block in request.system if isinstance(block, TextBlock)
            )
            if not system_prompt:
                system_prompt = None

    # Conversation messages
    for msg in request.messages:
        if isinstance(msg.content, str):
            messages.append(Message(role=msg.role, content=msg.content))
        else:
            text_parts: list[str] = []
            images: list[str] = []
            tool_calls: list[dict[str, Any]] = []

            for block in msg.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif hasattr(block, "source") and block.type == "image":
                    source = block.source
                    if isinstance(source, dict) and source.get("type") == "base64":
                        media_type = source.get("media_type", "image/jpeg")
                        data = source.get("data", "")
                        images.append(f"data:{media_type};base64,{data}")
                elif hasattr(block, "tool_use_id") and block.type == "tool_result":
                    tc = block.content
                    if isinstance(tc, list):
                        result_text = "\n".join(
                            b.text for b in tc if isinstance(b, TextBlock)
                        )
                    else:
                        result_text = tc or ""
                    messages.append(
                        Message(role="tool", content=result_text, tool_name=block.tool_use_id)
                    )
                elif hasattr(block, "id") and block.type == "tool_use":
                    tool_calls.append(
                        {
                            "function": {
                                "name": block.name,
                                "arguments": block.input,
                            }
                        }
                    )
                elif hasattr(block, "thinking") and block.type == "thinking":
                    pass

            if msg.role == "assistant" and tool_calls:
                messages.append(
                    Message(role="assistant", tool_calls=tool_calls)
                )
            elif text_parts or images:
                content = "\n".join(text_parts) if text_parts else ""
                if images:
                    messages.append(
                        Message(role=msg.role, content=content, images=images)
                    )
                else:
                    messages.append(Message(role=msg.role, content=content))

    # Tools
    ollama_tools: list[Tool] | None = None
    if request.tools:
        ollama_tools = []
        for tool in request.tools:
            ollama_tools.append(
                Tool(
                    function=Tool.Function(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=Tool.Function.Parameters(
                            type="object",
                            properties=tool.input_schema.properties,
                            required=tool.input_schema.required,
                        ),
                    )
                )
            )

    return messages, system_prompt, ollama_tools


def _ollama_chat_to_anthropic(
    response: ChatResponse, model_alias: str
) -> MessagesResponse:
    """Convert an Ollama ChatResponse to Anthropic MessagesResponse."""
    msg = response.message
    content: list[Any] = []

    if msg.thinking:
        content.append(
            ThinkingBlock(thinking=msg.thinking, signature=_SIGNATURE_PLACEHOLDER)
        )

    if msg.content:
        content.append(TextBlock(text=msg.content))

    if msg.tool_calls:
        for tc in msg.tool_calls:
            args = tc.function.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            content.append(
                ToolUseBlock(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    name=tc.function.name,
                    input=args,
                )
            )

    stop_reason = cast(
        "Literal['end_turn', 'max_tokens', 'stop_sequence', 'tool_use'] | None",
        _map_done_reason(response.done_reason),
    )
    return MessagesResponse(
        id=f"msg_{uuid.uuid4().hex[:16]}",
        model=model_alias,
        content=content,
        stop_reason=stop_reason,
        usage=Usage(
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        ),
    )


def _ollama_chunk_to_openai_chunk(
    chunk: ChatResponse, chunk_id: str
) -> dict[str, Any]:
    """Convert a streaming Ollama ChatResponse chunk to an OpenAI-format chunk."""
    oai_chunk: dict[str, Any] = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": 0,
        "model": chunk.model or "",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": None,
            }
        ],
    }

    delta: dict[str, Any] = {}
    msg = chunk.message

    if msg.thinking:
        delta["reasoning_content"] = msg.thinking

    if msg.content:
        delta["content"] = msg.content

    if msg.tool_calls:
        tool_calls = []
        for i, tc in enumerate(msg.tool_calls):
            args = tc.function.arguments
            if not isinstance(args, str):
                args = json.dumps(args)
            tool_calls.append(
                {
                    "index": i,
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": args},
                }
            )
        delta["tool_calls"] = tool_calls

    oai_chunk["choices"][0]["delta"] = delta

    if chunk.done:
        oai_chunk["choices"][0]["finish_reason"] = chunk.done_reason or "stop"
        oai_chunk["usage"] = {
            "prompt_tokens": chunk.prompt_eval_count or 0,
            "completion_tokens": chunk.eval_count or 0,
            "total_tokens": (chunk.prompt_eval_count or 0) + (chunk.eval_count or 0),
        }

    return oai_chunk


class OllamaBridge(Bridge):
    """Bridge to Ollama's native chat API via the ollama-python SDK."""

    name = "ollama"
    default_api_base = "http://127.0.0.1:11434"
    capabilities = VendorCapabilities(
        supports_vision=True,
        supports_reasoning=True,
        supports_tool_calls=True,
        supports_video=False,
        max_tokens=8192,
    )

    def __init__(
        self,
        api_key: str = "",
        api_base: str | None = None,
        model_alias: str = "",
        backend_model: str = "",
        keep_alive: str | float | None = None,
    ):
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            model_alias=model_alias,
            backend_model=backend_model,
        )
        self.keep_alive = keep_alive
        self._client = AsyncClient(host=self.api_base)

    def _build_options(self, request: MessagesRequest) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if request.max_tokens:
            options["num_predict"] = request.max_tokens
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.top_k is not None:
            options["top_k"] = request.top_k
        if request.stop_sequences:
            options["stop"] = list(request.stop_sequences)
        return options

    async def chat(self, request: MessagesRequest) -> MessagesResponse:
        try:
            messages, system_prompt, tools = _anthropic_messages_to_ollama(request)
        except Exception:
            _log_stderr(
                "error", "request translation failed",
                model_alias=self.model_alias,
                trace=traceback.format_exc(),
            )
            raise BridgeError(
                message="Failed to translate request for Ollama",
                status_code=502,
                error_type="api_error",
            )

        if system_prompt:
            messages.insert(0, Message(role="system", content=system_prompt))

        options = self._build_options(request)

        _log_stderr(
            "info", "ollama request",
            model_alias=self.model_alias,
            backend_model=self.backend_model,
            msg_count=len(messages),
            tool_count=len(tools) if tools else 0,
            streaming=False,
            keep_alive=str(self.keep_alive),
        )

        try:
            response: ChatResponse = await self._client.chat(
                model=self.backend_model,
                messages=messages,
                tools=tools,
                options=options if options else None,
                keep_alive=self.keep_alive,
                stream=False,
            )
        except Exception as e:
            _log_stderr(
                "error", "ollama SDK call failed",
                model_alias=self.model_alias,
                backend_model=self.backend_model,
                error=str(e),
                trace=traceback.format_exc(),
            )
            raise BridgeError(
                message=str(e),
                status_code=502,
                error_type="api_error",
            ) from e

        try:
            result = _ollama_chat_to_anthropic(response, self.model_alias)
        except Exception:
            _log_stderr(
                "error", "response translation failed",
                model_alias=self.model_alias,
                response_preview=str(response)[:1000],
                trace=traceback.format_exc(),
            )
            raise BridgeError(
                message="Failed to translate Ollama response",
                status_code=502,
                error_type="api_error",
            )

        _log_stderr(
            "info", "ollama response OK",
            model_alias=self.model_alias,
            content_blocks=len(result.content),
            stop_reason=result.stop_reason,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )
        return result

    async def chat_stream(
        self, request: MessagesRequest
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            messages, system_prompt, tools = _anthropic_messages_to_ollama(request)
        except Exception:
            _log_stderr(
                "error", "stream request translation failed",
                model_alias=self.model_alias,
                trace=traceback.format_exc(),
            )
            raise BridgeError(
                message="Failed to translate stream request for Ollama",
                status_code=502,
                error_type="api_error",
            )

        if system_prompt:
            messages.insert(0, Message(role="system", content=system_prompt))

        options = self._build_options(request)
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        _log_stderr(
            "info", "ollama stream request",
            model_alias=self.model_alias,
            backend_model=self.backend_model,
            msg_count=len(messages),
            tool_count=len(tools) if tools else 0,
            streaming=True,
            keep_alive=str(self.keep_alive),
        )

        try:
            stream = await self._client.chat(
                model=self.backend_model,
                messages=messages,
                tools=tools,
                options=options if options else None,
                keep_alive=self.keep_alive,
                stream=True,
            )
        except Exception as e:
            _log_stderr(
                "error", "ollama stream SDK call failed",
                model_alias=self.model_alias,
                backend_model=self.backend_model,
                error=str(e),
                trace=traceback.format_exc(),
            )
            raise BridgeError(
                message=str(e),
                status_code=502,
                error_type="api_error",
            ) from e

        chunk_count = 0
        async for chunk in stream:
            chunk_count += 1
            try:
                oai_chunk = _ollama_chunk_to_openai_chunk(chunk, chunk_id)
                yield {"type": "raw", "data": json.dumps(oai_chunk)}
            except Exception:
                _log_stderr(
                    "error", "chunk translation failed",
                    model_alias=self.model_alias,
                    chunk_index=chunk_count,
                    chunk_preview=str(chunk)[:500],
                    trace=traceback.format_exc()[:1200],
                )

        _log_stderr(
            "info", "ollama stream done",
            model_alias=self.model_alias,
            chunk_count=chunk_count,
        )

    async def close(self):
        await self._client.close()
