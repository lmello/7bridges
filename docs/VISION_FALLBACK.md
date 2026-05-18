# Vision Fallback — "See No Evil, Hear No Evil"

> *"I may be blind, but I can see through you."* — Richard Pryor, *See No Evil, Hear No Evil* (1989)

## What it is

The vision fallback is an experimental feature that gives **blind models** — backends without `supports_vision=True` — the ability to process images by delegating vision tasks to a separate VL (vision-language) backend.

## The problem

By default, when a non-vision backend like DeepSeek receives an image request, 7 Bridges returns a **soft 200 rejection** instead of a fatal 400 error. This preserves Claude Code's flow and gives the model guidance to fall back to OCR or DOM-based methods.

When enabled, the vision fallback goes further: it silently intercepts images, sends them to a vision-capable model, and replaces the `ImageBlock` with a `TextBlock` containing the description. The blind model never knows images were involved.

## Configuration

Set these environment variables:

| Variable | Default | Description |
|---|---|---|
| `SEVEN_BRIDGES_VISION_FALLBACK_ENABLED` | `false` | Enable the feature |
| `SEVEN_BRIDGES_VISION_FALLBACK_BACKEND` | `""` | VL backend spec: `kimi/<model>` or `ollama/<model>` |
| `SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT` | `60` | Per-image timeout in seconds |

### Example: Kimi K2.6 as eyes for DeepSeek

```bash
export SEVEN_BRIDGES_VISION_FALLBACK_ENABLED=true
export SEVEN_BRIDGES_VISION_FALLBACK_BACKEND=kimi/kimi-k2-6
export SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT=60
```

### Example: Local Ollama VL model

```bash
export SEVEN_BRIDGES_VISION_FALLBACK_ENABLED=true
export SEVEN_BRIDGES_VISION_FALLBACK_BACKEND=ollama/qwen3-vl:8b
export SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT=60
```

## How it works

```
Claude Code → 7 Bridges → DeepSeek (blind)
                    ↓  image detected, no vision support
              Kimi K2.6 (VL backend)
                    ↓  text description
              DeepSeek receives: "[Image: A login form with...]"
```

1. A request arrives with `ImageBlock`s
2. If the target backend doesn't support vision and fallback is enabled:
   - Each image is resized (max 1024px, JPEG quality 85) to prevent timeouts
   - A side request is sent to the configured VL backend
   - The VL response replaces the `ImageBlock` with a `TextBlock("[Image: ...]")`
3. The modified request (now image-free) proceeds to the original backend

## Prompt construction

The VL backend receives the **same text prompt** that accompanied the image in the original request. If there is no adjacent text, it falls back to `"describe this image in detail"`.

## Failure handling

If the VL backend call fails (timeout, error), the image is replaced with:

```
[Image: Image description unavailable — vision fallback failed]
```

This ensures the conversation continues rather than halting.

## Video

`video_in` is **not implemented**. Requests with video blocks receive a soft 200 rejection:

```
video_in is not implemented for model {backend_model}. No plans for video support at this time.
```

## Performance notes

- Image resizing is done in-memory via Pillow
- Each image triggers one VL backend call
- Timeout is per-image, not per-request
- Large screenshots (e.g. Playwright) are automatically downsized

## Cost considerations

Using Kimi K2.6 as a vision fallback adds cost per image turn. For local/self-hosted setups, an Ollama VL model like `qwen3-vl:8b` provides a zero-cost alternative at the expense of local GPU/CPU resources.
