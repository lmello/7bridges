"""FastAPI application entry point."""

import json
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from starlette.responses import Response

from seven_bridges.backends.base import Bridge, BridgeError
from seven_bridges.backends.deepseek import DeepSeekBridge
from seven_bridges.backends.kimi import KimiBridge
from seven_bridges.backends.ollama import OllamaBridge
from seven_bridges.backends.siliconflow import SiliconFlowBridge
from seven_bridges.config import ModelRoute, settings
from seven_bridges.debug import DebugMiddleware
from seven_bridges.models.anthropic import (
    CountTokensRequest,
    CountTokensResponse,
    MessagesRequest,
)
from seven_bridges.translation.request import request_has_images
from seven_bridges.translation.stream import translate_openai_stream
from seven_bridges.vision_fallback import (
    build_soft_reject_response,
    describe_images_in_request,
    request_has_video,
)


def _estimate_tokens(obj: Any) -> int:
    """Rough token count estimate for count_tokens endpoint.

    Uses ~4 chars per token heuristic. Good enough for Claude Code's
    statusline display; not for billing.
    """
    text = ""
    if isinstance(obj, str):
        text = obj
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                text += item.get("text", "")
                text += item.get("content", "")
                text += item.get("thinking", "")
            elif isinstance(item, str):
                text += item
    elif isinstance(obj, dict):
        text += obj.get("text", "")
        text += obj.get("content", "")
        text += obj.get("thinking", "")
    # ~4 chars per token for English/code, plus overhead
    return max(1, len(text) // 4 + len(text) // 100)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    yield


app = FastAPI(
    title="7 Bridges of Claude",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(DebugMiddleware)


def _log_diagnostic(kind: str, request_body: object, details: dict[str, Any]) -> None:
    """Write diagnostic info for debugging intermittent 400s."""
    from datetime import datetime

    diag_path = Path(__file__).parent.parent.parent / "logs" / "diagnostics.jsonl"
    diag_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "kind": kind,
        "request_preview": request_body
        if isinstance(request_body, dict)
        else str(request_body)[:500],
        "details": details,
    }
    with open(diag_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _get_bridge(route: ModelRoute) -> Bridge:
    """Instantiate the correct backend bridge for a model route."""
    kwargs = {
        "model_alias": route.alias,
        "backend_model": route.backend_model,
    }
    if route.bridge == "deepseek":
        if not settings.deepseek_api_key:
            raise BridgeError(
                "DEEPSEEK_API_KEY not configured",
                status_code=503,
                error_type="configuration_error",
            )
        return DeepSeekBridge(api_key=settings.deepseek_api_key, **kwargs)
    elif route.bridge == "kimi":
        if not settings.kimi_api_key:
            raise BridgeError(
                "KIMI_CODE_API_KEY not configured",
                status_code=503,
                error_type="configuration_error",
            )
        return KimiBridge(api_key=settings.kimi_api_key, **kwargs)
    elif route.bridge == "ollama":
        return OllamaBridge(
            api_base=settings.ollama_host,
            keep_alive=settings.ollama_keep_alive,
            **kwargs,
        )
    elif route.bridge == "siliconflow":
        if not settings.siliconflow_api_key:
            raise BridgeError(
                "SILICONFLOW_API_KEY not configured",
                status_code=503,
                error_type="configuration_error",
            )
        return SiliconFlowBridge(api_key=settings.siliconflow_api_key, **kwargs)
    else:
        raise BridgeError(
            f"Unknown bridge: {route.bridge}",
            status_code=500,
            error_type="internal_error",
        )


@app.post("/v1/messages", response_model=None)
async def messages(
    request: Request,
    x_api_key: str = Header(default="", alias="x-api-key"),
    authorization: str = Header(default=""),
) -> Response:
    """Anthropic Messages API compatible endpoint."""
    # Auth: accept Anthropic-style x-api-key or Bearer token
    api_key = x_api_key or authorization.replace("Bearer ", "")
    if api_key != settings.api_key:
        return JSONResponse(
            status_code=401,
            content={
                "type": "error",
                "error": {"type": "authentication_error", "message": "Invalid API key"},
            },
        )

    body = await request.json()
    try:
        anthropic_request = MessagesRequest.model_validate(body)
    except ValidationError as exc:
        # Log validation errors for debugging intermittent 400s
        _log_diagnostic("validation_error", body, {"error": str(exc)})
        raise

    route = settings.resolve_model(anthropic_request.model)
    if route is None:
        _log_diagnostic("unknown_model", body, {"model": anthropic_request.model})
        return JSONResponse(
            status_code=400,
            content={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": f"Unknown model: {anthropic_request.model}",
                },
            },
        )

    bridge = _get_bridge(route)
    request.state.bridge_name = route.bridge
    request.state.resolved_backend_model = route.backend_model

    # Validate request against vendor capabilities
    has_images = request_has_images(anthropic_request)
    has_video = request_has_video(anthropic_request)

    if (has_images or has_video) and not bridge.capabilities.supports_vision:
        # Vision fallback — experimental "See No Evil, Hear No Evil" feature
        if settings.vision_fallback_enabled and has_images and settings.vision_fallback_backend:
            # Parse backend spec: "kimi/kimi-k2-6" or "ollama/qwen3-vl:8b"
            parts = settings.vision_fallback_backend.split("/", 1)
            if len(parts) == 2:
                vl_backend, vl_model = parts
                anthropic_request = await describe_images_in_request(
                    anthropic_request,
                    backend=vl_backend,
                    model=vl_model,
                    timeout=settings.vision_fallback_timeout,
                )
            else:
                # Malformed backend spec — fall through to soft reject
                return JSONResponse(
                    content=build_soft_reject_response(route.backend_model, has_video),
                )
        else:
            # Soft reject: return 200 with guidance instead of 400 fatal error
            return JSONResponse(
                content=build_soft_reject_response(route.backend_model, has_video),
            )

    # Pass debug log path to bridge for outgoing request logging
    bridge._debug_log_path = getattr(request.state, "debug_log_path", None)

    if anthropic_request.stream:
        stream = bridge.chat_stream(anthropic_request)
        translated = translate_openai_stream(stream, route.alias)

        return StreamingResponse(
            translated,
            media_type="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
            },
        )
    else:
        response = await bridge.chat(anthropic_request)
        return JSONResponse(content=response.model_dump())


@app.post("/v1/messages/count_tokens")
async def count_tokens(
    request: Request,
    x_api_key: str = Header(default=""),
) -> JSONResponse:
    """Count tokens in a message batch (local estimation).

    Upstream vendors (DeepSeek, Kimi) do not expose a native token-count API.
    We use a heuristic (~4 chars/token) sufficient for Claude Code's
    statusline display. Not for billing.
    """
    if x_api_key != settings.api_key:
        return JSONResponse(
            status_code=401,
            content={
                "type": "error",
                "error": {"type": "authentication_error", "message": "Invalid API key"},
            },
        )

    body = await request.json()
    try:
        req = CountTokensRequest.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "type": "error",
                "error": {"type": "invalid_request_error", "message": str(exc)},
            },
        )

    total = 0
    # Messages
    for msg in req.messages:
        total += _estimate_tokens(msg.content)
    # System prompt
    if req.system:
        total += _estimate_tokens(req.system)
    # Tools schema (rough: ~50 tokens per tool)
    if req.tools:
        total += len(req.tools) * 50

    resp = CountTokensResponse(input_tokens=total)
    return JSONResponse(content=resp.model_dump())


async def _list_models() -> dict[str, Any]:
    """List available models (Anthropic compatible)."""
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _alias, route in settings.model_routes.items():
        if route.alias not in seen:
            seen.add(route.alias)
            models.append(
                {
                    "type": "model",
                    "id": route.alias,
                    "display_name": route.display_name,
                    "context_window": route.context_window,
                    "max_output_tokens": route.max_output_tokens,
                }
            )
    return {"data": models, "has_more": False, "first_id": None, "last_id": None}


@app.get("/v1/models")
async def list_models(request: Request) -> dict[str, Any]:
    return await _list_models()


@app.head("/v1/models")
async def head_list_models(request: Request) -> Response:
    """HEAD support for /v1/models — Claude Code probes endpoints."""
    return Response(status_code=200)


@app.get("/models")
async def list_models_alias(request: Request) -> dict[str, Any]:
    """Alias for /v1/models (some clients hit /models directly)."""
    return await _list_models()


@app.head("/models")
async def head_list_models_alias(request: Request) -> Response:
    """HEAD support for /models alias."""
    return Response(status_code=200)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.head("/health")
async def head_health() -> Response:
    """HEAD support for /health — Claude Code connectivity checks."""
    return Response(status_code=200)


@app.head("/")
async def head_root() -> Response:
    """HEAD support for root — Claude Code connectivity checks."""
    return Response(status_code=200)


@app.head("/v1/messages")
async def head_messages() -> Response:
    """HEAD support for /v1/messages — Claude Code probes before POST."""
    return Response(status_code=200)


@app.exception_handler(BridgeError)
async def bridge_error_handler(request: Request, exc: BridgeError) -> JSONResponse:
    _log_diagnostic(
        "upstream_error",
        {"url": str(request.url), "method": request.method},
        {"status": exc.status_code, "type": exc.error_type, "message": exc.message[:500]},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "error",
            "error": {
                "type": exc.error_type,
                "message": exc.message,
            },
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    _log_diagnostic(
        "validation_error_handler",
        {"url": str(request.url), "method": request.method},
        {"message": str(exc)[:500]},
    )
    return JSONResponse(
        status_code=400,
        content={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": str(exc),
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    _log_diagnostic(
        "unhandled_error",
        {"url": str(request.url), "method": request.method},
        {"error": str(exc), "traceback": traceback.format_exc()},
    )
    return JSONResponse(
        status_code=500,
        content={
            "type": "error",
            "error": {
                "type": "internal_error",
                "message": str(exc),
            },
        },
    )
