"""Tests for the vision fallback "See No Evil, Hear No Evil" feature."""

import base64
import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from seven_bridges.models.anthropic import (
    ContentBlock,
    ImageBlock,
    Message,
    MessagesRequest,
    TextBlock,
    ToolResultBlock,
)
from seven_bridges.vision_fallback import (
    _build_prompt_for_image,
    _image_block_to_data_uri,
    _resize_image,
    build_soft_reject_response,
    describe_images_in_request,
    request_has_video,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_image(
    width: int = 100,
    height: int = 100,
    color: tuple[int, int, int] = (255, 0, 0),
) -> str:
    """Create a base64-encoded PNG image."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_jpeg_image(
    width: int = 100,
    height: int = 100,
    color: tuple[int, int, int] = (0, 255, 0),
) -> str:
    """Create a base64-encoded JPEG image."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _make_image_block(b64_data: str, media_type: str = "image/png") -> ImageBlock:
    return ImageBlock(
        source={
            "type": "base64",
            "media_type": media_type,
            "data": b64_data,
        }
    )


# ---------------------------------------------------------------------------
# Image resizing
# ---------------------------------------------------------------------------


def test_resize_image_png():
    """PNG images are resized and converted to JPEG."""
    b64 = _make_png_image(width=2000, height=1500)
    data_uri = f"data:image/png;base64,{b64}"
    result = _resize_image(data_uri)

    assert result.startswith("data:image/jpeg;base64,")
    # Decode and check dimensions
    raw = base64.b64decode(result.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    assert img.format == "JPEG"
    max_dim = max(img.width, img.height)
    assert max_dim <= 1024


def test_resize_image_jpeg():
    """JPEG images are resized correctly."""
    b64 = _make_jpeg_image(width=1500, height=2000)
    data_uri = f"data:image/jpeg;base64,{b64}"
    result = _resize_image(data_uri)

    assert result.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(result.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    assert img.format == "JPEG"
    max_dim = max(img.width, img.height)
    assert max_dim <= 1024


def test_resize_image_no_resize_needed():
    """Small images are not upscaled."""
    b64 = _make_png_image(width=100, height=100)
    data_uri = f"data:image/png;base64,{b64}"
    result = _resize_image(data_uri)

    raw = base64.b64decode(result.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    assert img.width == 100
    assert img.height == 100


def test_resize_image_rgba_converted_to_rgb():
    """RGBA PNGs are converted to RGB JPEG."""
    img = Image.new("RGBA", (500, 500), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    data_uri = f"data:image/png;base64,{b64}"
    result = _resize_image(data_uri)

    raw = base64.b64decode(result.split(",", 1)[1])
    img2 = Image.open(io.BytesIO(raw))
    assert img2.mode == "RGB"


# ---------------------------------------------------------------------------
# Data URI extraction
# ---------------------------------------------------------------------------


def test_image_block_to_data_uri_valid():
    b64 = _make_png_image()
    block = _make_image_block(b64, "image/png")
    uri = _image_block_to_data_uri(block)
    assert uri == f"data:image/png;base64,{b64}"


def test_image_block_to_data_uri_invalid_source_type():
    block = ImageBlock(source={"type": "url", "url": "http://example.com/img.png"})
    assert _image_block_to_data_uri(block) is None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def test_build_prompt_with_adjacent_text():
    """Adjacent text blocks are used as the VL prompt."""
    img = _make_image_block(_make_png_image())
    blocks: list[ContentBlock] = [TextBlock(text="What color is this?"), img]
    prompt = _build_prompt_for_image(img, blocks)
    assert prompt == "What color is this?"


def test_build_prompt_no_text_fallback():
    """Without adjacent text, use default describe prompt."""
    img = _make_image_block(_make_png_image())
    blocks: list[ContentBlock] = [img]
    prompt = _build_prompt_for_image(img, blocks)
    assert prompt == "describe this image in detail"


def test_build_prompt_with_tool_result_context():
    """Tool result text is included as context."""
    img = _make_image_block(_make_png_image())
    tool_result = ToolResultBlock(
        tool_use_id="tool_1",
        content=[TextBlock(text="Screenshot of login page")],
    )
    blocks: list[ContentBlock] = [tool_result, img]
    prompt = _build_prompt_for_image(img, blocks)
    assert "Screenshot of login page" in prompt


# ---------------------------------------------------------------------------
# Soft reject response
# ---------------------------------------------------------------------------


def test_soft_reject_response_format():
    """Soft reject returns a valid Anthropic MessagesResponse shape."""
    resp = build_soft_reject_response("deepseek-v4-pro")
    assert resp["type"] == "message"
    assert resp["role"] == "assistant"
    assert resp["model"] == "deepseek-v4-pro"
    assert resp["stop_reason"] == "end_turn"
    assert len(resp["content"]) == 1
    assert resp["content"][0]["type"] == "text"
    assert "vision_in" in resp["content"][0]["text"]
    assert "deepseek-v4-pro" in resp["content"][0]["text"]


def test_video_not_implemented_response():
    """Video requests get a NOT IMPLEMENTED message."""
    resp = build_soft_reject_response("deepseek-v4-pro", has_video=True)
    assert "video_in is not implemented" in resp["content"][0]["text"]


# ---------------------------------------------------------------------------
# Video detection (placeholder)
# ---------------------------------------------------------------------------


def test_request_has_video_no_video():
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content="Hello")],
    )
    assert request_has_video(req) is False


# ---------------------------------------------------------------------------
# describe_images_in_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_describe_images_replaces_image_blocks():
    """ImageBlocks are replaced with TextBlock descriptions."""
    img_b64 = _make_png_image()
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    TextBlock(text="What do you see?"),
                    _make_image_block(img_b64),
                ],
            )
        ],
    )

    with patch(
        "seven_bridges.vision_fallback._describe_image",
        new_callable=AsyncMock,
        return_value="A red square",
    ):
        result = await describe_images_in_request(
            req, backend="kimi", model="kimi-k2-6", timeout=30.0
        )

    assert len(result.messages) == 1
    content = result.messages[0].content
    assert isinstance(content, list)
    assert len(content) == 2
    assert isinstance(content[0], TextBlock)
    assert content[0].text == "What do you see?"
    assert isinstance(content[1], TextBlock)
    assert "A red square" in content[1].text
    assert content[1].text.startswith("[Image:")


@pytest.mark.asyncio
async def test_describe_images_in_tool_result():
    """Images inside ToolResultBlock are also described."""
    img_b64 = _make_png_image()
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[
                    ToolResultBlock(
                        tool_use_id="tool_1",
                        content=[
                            TextBlock(text="Here is the screenshot:"),
                            _make_image_block(img_b64),
                        ],
                    )
                ],
            )
        ],
    )

    with patch(
        "seven_bridges.vision_fallback._describe_image",
        new_callable=AsyncMock,
        return_value="A red square in a tool result",
    ):
        result = await describe_images_in_request(
            req, backend="ollama", model="qwen3-vl:8b", timeout=30.0
        )

    content = result.messages[0].content
    assert isinstance(content, list)
    tool_result = content[0]
    assert isinstance(tool_result, ToolResultBlock)
    assert isinstance(tool_result.content, list)
    assert isinstance(tool_result.content[0], TextBlock)
    assert tool_result.content[0].text == "Here is the screenshot:"
    assert isinstance(tool_result.content[1], TextBlock)
    assert "A red square in a tool result" in tool_result.content[1].text


@pytest.mark.asyncio
async def test_describe_images_preserves_other_fields():
    """Non-image fields in MessagesRequest are preserved."""
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[Message(role="user", content=[TextBlock(text="Hello")])],
        max_tokens=512,
        temperature=0.7,
        system="Be helpful.",
    )

    with patch(
        "seven_bridges.vision_fallback._describe_image",
        new_callable=AsyncMock,
        return_value="nothing",
    ):
        result = await describe_images_in_request(
            req, backend="kimi", model="kimi-k2-6", timeout=30.0
        )

    assert result.max_tokens == 512
    assert result.temperature == 0.7
    assert result.system == "Be helpful."


@pytest.mark.asyncio
async def test_describe_images_handles_vl_failure():
    """If the VL backend fails, replace with a fallback note."""
    img_b64 = _make_png_image()
    req = MessagesRequest(
        model="claude-sonnet-4-6",
        messages=[
            Message(
                role="user",
                content=[_make_image_block(img_b64)],
            )
        ],
    )

    with patch(
        "seven_bridges.vision_fallback._describe_image",
        new_callable=AsyncMock,
        side_effect=Exception("timeout"),
    ):
        result = await describe_images_in_request(
            req, backend="kimi", model="kimi-k2-6", timeout=30.0
        )

    content = result.messages[0].content
    assert isinstance(content, list)
    assert isinstance(content[0], TextBlock)
    assert "vision fallback failed" in content[0].text


# ---------------------------------------------------------------------------
# describe_images_in_request with real image file
# ---------------------------------------------------------------------------


def test_describe_images_with_real_png():
    """Integration-style test using the ocak-forge.png sample.

    We only test the resizing pipeline here, not the actual VL backend call.
    """
    from pathlib import Path

    sample_path = Path("/Users/said/Dev/vibe/ocak-forge/docs/images/ocak-forge.png")
    if not sample_path.exists():
        pytest.skip("Sample image not available")

    raw = sample_path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    data_uri = f"data:image/png;base64,{b64}"

    resized = _resize_image(data_uri)
    assert resized.startswith("data:image/jpeg;base64,")

    raw_resized = base64.b64decode(resized.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw_resized))
    assert img.format == "JPEG"
    assert max(img.width, img.height) <= 1024
