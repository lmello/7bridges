"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from starlette.responses import Response

from seven_bridges.backends.base import Bridge, BridgeError
from seven_bridges.backends.deepseek import DeepSeekBridge
from seven_bridges.backends.kimi import KimiBridge
from seven_bridges.config import ModelRoute, settings
from seven_bridges.debug import DebugMiddleware
from seven_bridges.models.anthropic import MessagesRequest
from seven_bridges.translation.request import request_has_images
from seven_bridges.translation.stream import translate_openai_stream


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
    anthropic_request = MessagesRequest.model_validate(body)

    route = settings.model_routes.get(anthropic_request.model)
    if route is None:
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

    # Validate request against vendor capabilities
    if request_has_images(anthropic_request) and not bridge.capabilities.supports_vision:
        return JSONResponse(
            status_code=400,
            content={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": f"Model {route.alias} does not support image input",
                },
            },
        )

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
