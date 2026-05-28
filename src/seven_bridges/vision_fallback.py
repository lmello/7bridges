"""Vision fallback — give blind models eyes via a VL backend.

Experimental feature. When a non-vision backend receives an image request,
we can optionally route the image to a vision-capable model (Kimi, Ollama VL)
and replace the ImageBlock with a TextBlock containing the description.

See: docs/vision-fallback.md for configuration.
"""

import asyncio
import base64
import io
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

import httpx
from PIL import Image

from seven_bridges.backends.base import BridgeError
from seven_bridges.models.anthropic import (
    ContentBlock,
    ImageBlock,
    Message,
    MessagesRequest,
    TextBlock,
    ToolResultBlock,
)


def _log_stderr(level: str, message: str, **details: Any) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "level": level,
        "bridge": "vision_fallback",
        "msg": message,
        **details,
    }
    print(json.dumps(entry, ensure_ascii=False, default=str), file=sys.stderr)


# ---------------------------------------------------------------------------
# Image resizing
# ---------------------------------------------------------------------------

# Max dimension (width or height) for images sent to VL backend.
# Playwright screenshots at full resolution are huge; resizing prevents
# timeouts and keeps costs reasonable.
_VL_MAX_DIMENSION: int = int(os.environ.get("SEVEN_BRIDGES_VL_MAX_DIMENSION", "1024"))
_VL_JPEG_QUALITY: int = int(os.environ.get("SEVEN_BRIDGES_VL_JPEG_QUALITY", "85"))


def _resize_image(base64_data: str) -> str:
    """Resize an image to reduce payload size for VL backends.

    Returns base64-encoded JPEG data URI.
    """
    # Strip data URI prefix if present
    if base64_data.startswith("data:"):
        # data:image/png;base64,...
        parts = base64_data.split(",", 1)
        if len(parts) == 2:
            base64_data = parts[1]

    raw = base64.b64decode(base64_data)
    img: Image.Image = Image.open(io.BytesIO(raw))

    # Convert to RGB if necessary (e.g. RGBA, P mode)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if larger than max dimension
    max_dim = _VL_MAX_DIMENSION
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    quality = _VL_JPEG_QUALITY
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    resized = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{resized}"


# ---------------------------------------------------------------------------
# VL backend calling
# ---------------------------------------------------------------------------


async def _call_kimi_vision(
    api_key: str,
    model: str,
    prompt: str,
    image_data_uri: str,
    timeout: float,
) -> str:
    """Call Kimi Code API vision endpoint."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                ],
            }
        ],
        "max_tokens": 4096,
    }

    _log_stderr(
        "info",
        "vision fallback kimi request",
        model=model,
        prompt_len=len(prompt),
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.kimi.com/coding/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "claude-code/0.1.0",
                },
                json=payload,
                timeout=timeout,
            )
        except asyncio.CancelledError:
            _log_stderr("info", "vision fallback kimi cancelled by client disconnect", model=model)
            raise

        if response.status_code != 200:
            raise BridgeError(
                message=f"Kimi vision fallback failed: {response.text}",
                status_code=response.status_code,
                error_type="api_error",
            )

        data = response.json()
        return str(data["choices"][0]["message"]["content"])


async def _call_ollama_vision(
    host: str,
    model: str,
    prompt: str,
    image_data_uri: str,
    timeout: float,
) -> str:
    """Call Ollama vision endpoint.

    Ollama expects images as base64 strings (without data URI prefix).
    """
    # Strip data URI prefix for Ollama
    image_b64 = image_data_uri
    if image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "keep_alive": 0,  # unload model immediately after response
    }

    _log_stderr(
        "info",
        "vision fallback ollama request",
        model=model,
        prompt_len=len(prompt),
        image_len=len(image_b64),
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{host}/api/chat",
                json=payload,
                timeout=httpx.Timeout(timeout, connect=10.0),
            )
        except asyncio.CancelledError:
            _log_stderr(
                "info",
                "vision fallback ollama cancelled by client disconnect",
                model=model,
            )
            raise
        except httpx.TimeoutException:
            _log_stderr(
                "error",
                "vision fallback ollama timed out",
                model=model,
                timeout=timeout,
            )
            raise BridgeError(
                message=f"Ollama vision fallback timed out after {timeout}s",
                status_code=504,
                error_type="timeout_error",
            ) from None
        except Exception as exc:
            _log_stderr(
                "error",
                "vision fallback ollama request failed",
                model=model,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise BridgeError(
                message=f"Ollama vision fallback error: {exc}",
                status_code=502,
                error_type="api_error",
            ) from exc

        if response.status_code != 200:
            _log_stderr(
                "error",
                "vision fallback ollama bad status",
                model=model,
                status_code=response.status_code,
                response_preview=response.text[:500],
            )
            raise BridgeError(
                message=f"Ollama vision fallback failed: {response.text}",
                status_code=response.status_code,
                error_type="api_error",
            )

        data = response.json()
        return str(data["message"]["content"])


async def _describe_image(
    backend: str,
    model: str,
    prompt: str,
    image_data_uri: str,
    timeout: float,
) -> str:
    """Route image description to the configured VL backend."""
    if backend == "kimi":
        api_key = os.environ.get("KIMI_CODE_API_KEY", "")
        if not api_key:
            raise BridgeError(
                message="KIMI_CODE_API_KEY not configured for vision fallback",
                status_code=503,
                error_type="configuration_error",
            )
        return await _call_kimi_vision(api_key, model, prompt, image_data_uri, timeout)

    if backend == "ollama":
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        return await _call_ollama_vision(host, model, prompt, image_data_uri, timeout)

    raise BridgeError(
        message=f"Unknown vision fallback backend: {backend}",
        status_code=500,
        error_type="internal_error",
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt_for_image(
    image_block: ImageBlock,
    sibling_blocks: list[ContentBlock],
) -> str:
    """Build the prompt to send to the VL backend.

    If there is adjacent text in the same message, use it as context.
    Otherwise fall back to a generic describe prompt.
    """
    texts: list[str] = []
    for block in sibling_blocks:
        if block is image_block:
            continue
        if isinstance(block, TextBlock):
            texts.append(block.text)
        elif isinstance(block, ToolResultBlock):
            # Include tool result text for context
            if isinstance(block.content, str):
                texts.append(block.content)
            elif isinstance(block.content, list):
                for item in block.content:
                    if isinstance(item, TextBlock):
                        texts.append(item.text)

    joined = "\n".join(t.strip() for t in texts if t.strip())
    if joined:
        return joined
    return "describe this image in detail"


# ---------------------------------------------------------------------------
# Image extraction and replacement
# ---------------------------------------------------------------------------


def _image_block_to_data_uri(image_block: ImageBlock) -> str | None:
    """Convert an ImageBlock source dict to a data URI string."""
    source = image_block.source
    if not isinstance(source, dict):
        return None
    if source.get("type") == "base64":
        media_type = source.get("media_type", "image/jpeg")
        data = source.get("data", "")
        return f"data:{media_type};base64,{data}"
    return None


async def _process_message_images(
    msg: Message,
    backend: str,
    model: str,
    timeout: float,
) -> Message:
    """Replace all ImageBlocks in a message with TextBlock descriptions."""
    if isinstance(msg.content, str):
        return msg

    new_blocks: list[ContentBlock] = []
    for block in msg.content:
        if isinstance(block, ImageBlock):
            data_uri = _image_block_to_data_uri(block)
            if data_uri:
                prompt = _build_prompt_for_image(block, msg.content)
                resized = _resize_image(data_uri)
                try:
                    description = await _describe_image(backend, model, prompt, resized, timeout)
                except Exception:
                    # If VL fails, replace with a fallback note so the
                    # conversation can continue rather than erroring out.
                    description = "[Image description unavailable — vision fallback failed]"
                new_blocks.append(TextBlock(text=f"[Image: {description}]"))
            else:
                new_blocks.append(TextBlock(text="[Image: unsupported image format]"))
        elif isinstance(block, ToolResultBlock):
            new_tool_result = await _process_tool_result_images(block, backend, model, timeout)
            new_blocks.append(new_tool_result)
        else:
            new_blocks.append(block)

    return Message(role=msg.role, content=new_blocks)


async def _process_tool_result_images(
    block: ToolResultBlock,
    backend: str,
    model: str,
    timeout: float,
) -> ToolResultBlock:
    """Replace ImageBlocks inside a ToolResultBlock with TextBlock descriptions."""
    if not isinstance(block.content, list):
        return block

    new_content: list[TextBlock | ImageBlock] = []
    for item in block.content:
        if isinstance(item, ImageBlock):
            data_uri = _image_block_to_data_uri(item)
            if data_uri:
                # For tool results, we don't have sibling text in the same
                # tool result, so use the default prompt.
                prompt = "describe this image in detail"
                resized = _resize_image(data_uri)
                try:
                    description = await _describe_image(backend, model, prompt, resized, timeout)
                except Exception:
                    description = "[Image description unavailable — vision fallback failed]"
                new_content.append(TextBlock(text=f"[Image: {description}]"))
            else:
                new_content.append(TextBlock(text="[Image: unsupported image format]"))
        else:
            new_content.append(item)

    return ToolResultBlock(
        tool_use_id=block.tool_use_id,
        content=new_content,
        is_error=block.is_error,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SOFT_REJECT_MESSAGE_TEMPLATE: str = (
    "vision_in (image_in, video_in) not supported by {backend_model}. "
    "Please use OCR or DOM methods to handle your request locally."
)

VIDEO_NOT_IMPLEMENTED_MESSAGE: str = (
    "video_in is not implemented for model {backend_model}. "
    "No plans for video support at this time."
)


def request_has_video(request: MessagesRequest) -> bool:
    """Check if the request contains any video blocks.

    Currently a placeholder — video_in is not implemented.
    """
    # Anthropic video blocks would have type "video" in content.
    # We don't have a VideoBlock model yet; this is a structural check.
    for msg in request.messages:
        if isinstance(msg.content, list):
            for block in msg.content:
                if hasattr(block, "type") and getattr(block, "type", None) == "video":
                    return True
    return False


def build_soft_reject_response(backend_model: str, has_video: bool = False) -> dict[str, Any]:
    """Build a synthetic Anthropic MessagesResponse for soft rejection.

    Returns a dict that serializes as a valid Messages API response.
    """
    if has_video:
        message = VIDEO_NOT_IMPLEMENTED_MESSAGE.format(backend_model=backend_model)
    else:
        message = SOFT_REJECT_MESSAGE_TEMPLATE.format(backend_model=backend_model)

    return {
        "id": "msg_7bridges_soft_reject",
        "type": "message",
        "role": "assistant",
        "model": backend_model,
        "content": [{"type": "text", "text": message}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": len(message.split())},
    }


def _strip_message_images(msg: Message) -> Message:
    """Replace ImageBlocks with placeholder TextBlocks (no external calls)."""
    if isinstance(msg.content, str):
        return msg

    new_blocks: list[ContentBlock] = []
    for block in msg.content:
        if isinstance(block, ImageBlock):
            new_blocks.append(TextBlock(text="[image]"))
        elif isinstance(block, ToolResultBlock):
            if isinstance(block.content, list):
                new_tool_content: list[TextBlock | ImageBlock] = []
                for item in block.content:
                    if isinstance(item, ImageBlock):
                        new_tool_content.append(TextBlock(text="[image]"))
                    else:
                        new_tool_content.append(item)
                new_blocks.append(
                    ToolResultBlock(
                        tool_use_id=block.tool_use_id,
                        content=new_tool_content,
                        is_error=block.is_error,
                    )
                )
            else:
                new_blocks.append(block)
        else:
            new_blocks.append(block)

    return Message(role=msg.role, content=new_blocks)


def strip_images_from_request(request: MessagesRequest) -> MessagesRequest:
    """Remove all images from a request, replacing them with [image] placeholders.

    Used when vision fallback is disabled so conversations with image history
    can continue against non-vision backends.
    """
    new_messages: list[Message] = []
    for msg in request.messages:
        new_messages.append(_strip_message_images(msg))

    return MessagesRequest(
        model=request.model,
        messages=new_messages,
        max_tokens=request.max_tokens,
        system=request.system,
        metadata=request.metadata,
        stop_sequences=request.stop_sequences,
        stream=request.stream,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        tool_choice=request.tool_choice,
        tools=request.tools,
        thinking=request.thinking,
    )


async def describe_images_in_request(
    request: MessagesRequest,
    backend: str,
    model: str,
    timeout: float,
) -> MessagesRequest:
    """Replace all images in a request with VL-generated descriptions.

    Returns a new MessagesRequest with ImageBlocks replaced by TextBlocks.
    """
    new_messages: list[Message] = []
    for msg in request.messages:
        processed = await _process_message_images(msg, backend, model, timeout)
        new_messages.append(processed)

    # Rebuild the request preserving all other fields
    return MessagesRequest(
        model=request.model,
        messages=new_messages,
        max_tokens=request.max_tokens,
        system=request.system,
        metadata=request.metadata,
        stop_sequences=request.stop_sequences,
        stream=request.stream,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        tool_choice=request.tool_choice,
        tools=request.tools,
        thinking=request.thinking,
    )
