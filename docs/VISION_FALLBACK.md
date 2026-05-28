# Vision Fallback — "See No Evil, Hear No Evil"

> *"I may be blind, but I can see through you."* — Richard Pryor, *See No Evil, Hear No Evil* (1989)

## What it is

The vision fallback is an **experimental** feature that gives **blind models** — backends without `supports_vision=True` like DeepSeek — the ability to process images by making a **separate API call** to a vision-capable model.

When your main workhorse (e.g. DeepSeek) receives an image it can't handle, 7 Bridges can transparently route that image to a VL (vision-language) backend — **Kimi K2.6** or an **Ollama VL model** — get a text description, and substitute it into the conversation before forwarding to the original backend. The blind model never knows images were involved.

## The problem

When Claude Code sends a screenshot or image to a non-vision backend, the upstream returns an error. Before this feature, 7 Bridges propagated that as a **fatal 400 Bad Request**, which caused Claude Code to halt all operations and lose conversation progress.

Now there are two graceful paths:

### Path 1: Soft reject (default)

Return **200 OK** with a guidance message:

```
vision_in (image_in, video_in) not supported by {backend_model}.
Please use OCR or DOM methods to handle your request locally.
```

This lets the conversation continue. The model can fall back to text-based tools (DOM parsing, OCR scripts, etc.).

### Path 2: Vision fallback (opt-in)

When enabled via environment variable, images are **intercepted and described** by a separate VL model before reaching the blind backend:

```
Claude Code → 7 Bridges → DeepSeek (blind)
                    ↓
              [ImageBlock detected, no vision support]
                    ↓
         Kimi K2.6 or Ollama gemma4:e4b (VL backend)
                    ↓
         [separate API call with resized image + prompt]
                    ↓
         "A login form with email and password fields..."
                    ↓
         DeepSeek receives: "[Image: A login form with...]"
```

## How the separate API call works

This is **not** model routing in the traditional sense. The original request is **paused**, a **new independent request** is sent to the VL backend, and its text response is grafted back into the original request:

1. Request arrives with `ImageBlock`s for a non-vision backend (e.g. `claude-sonnet-4-6` → DeepSeek)
2. 7 Bridges detects the mismatch: `supports_vision=False` but request contains images
3. For each image:
   - Extract base64 data from the `ImageBlock`
   - **Resize** to max 1024px and convert to JPEG quality 85 (prevents timeouts on large screenshots)
   - Build a prompt from adjacent text in the same message (or fall back to `"describe this image in detail"`)
   - **Fire a separate async HTTP request** to the configured VL backend with the image + prompt
   - Wait up to `SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT` seconds (default: 60s)
4. Replace each `ImageBlock` with a `TextBlock("[Image: {description}]")`
5. Forward the modified request (now image-free) to the original backend

The VL backend call is **fully independent** — it uses its own HTTP client, auth headers, and endpoint. Kimi calls go to `api.kimi.com/coding/v1`, Ollama calls go to your local `OLLAMA_HOST`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SEVEN_BRIDGES_VISION_FALLBACK_ENABLED` | `false` | Enable the feature |
| `SEVEN_BRIDGES_VISION_FALLBACK_BACKEND` | `""` | VL backend spec: `kimi/<model>` or `ollama/<model>` |
| `SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT` | `120` | Per-image timeout in seconds |
| `SEVEN_BRIDGES_VISION_FALLBACK_OLLAMA_CTX` | `4096` | Context window size for Ollama VL calls. Smaller values reduce memory pressure and avoid GPU deadlocks. |

### Example: Kimi K2.6 as eyes for DeepSeek

```bash
export SEVEN_BRIDGES_VISION_FALLBACK_ENABLED=true
export SEVEN_BRIDGES_VISION_FALLBACK_BACKEND=kimi/kimi-k2-6
export SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT=60
```

This means: when DeepSeek (your main model) receives an image, 7 Bridges will make a **side call to Kimi K2.6** to describe it, then pass that description to DeepSeek as text.

### Example: Local Ollama VL model

```bash
export SEVEN_BRIDGES_VISION_FALLBACK_ENABLED=true
export SEVEN_BRIDGES_VISION_FALLBACK_BACKEND=ollama/gemma4:e4b
export SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT=120
```

This uses your **local Ollama instance** as the vision backend — zero per-call cost, but requires GPU/CPU resources to run the VL model.

## Supported image formats

The image processor auto-detects format from bytes using Pillow, so it handles:
- **PNG** (including RGBA with alpha channel → converted to RGB)
- **JPEG**
- **WEBP**, **BMP**, and any other format Pillow supports

No file extension inference is needed — the base64 payload is decoded and inspected directly.

## Prompt construction

The VL backend receives the **same text prompt** that accompanied the image in the original request. For example, if the user message is:

```
"What color is the button?" + [ImageBlock: screenshot]
```

The VL backend gets:
```
"What color is the button?" + [Image: screenshot]
```

This lets the VL model answer contextually rather than just describing generically. If there is no adjacent text, it falls back to `"describe this image in detail"`.

## Failure handling

If the VL backend call fails (timeout, network error, 5xx), the image is replaced with:

```
[Image: Image description unavailable — vision fallback failed]
```

The conversation continues rather than halting. This is a deliberate choice: a degraded experience beats a dead one.

## Video

`video_in` is **not implemented**. Requests with video blocks receive a soft 200 rejection:

```
video_in is not implemented for model {backend_model}. No plans for video support at this time.
```

## Image deduplication and caching

Identical images (same SHA256 hash of the resized JPEG) are cached in an append-only JSONL file at `/tmp/ollama-vision-fallback.jsonl`. Before making any VL backend call, 7 Bridges checks this cache. A cache hit returns instantly — no API call, no GPU usage, no cost.

The cache survives across:

- **Multiple requests** within the same session
- **Claude Code restarts and compactions** (when images are re-sent from history)
- **7 Bridges restarts** (module reloads the file on startup)
- **System reboots** (until macOS cleans `/tmp`)

This eliminates redundant VL calls when:
- Claude Code re-sends the same screenshot from cached conversation history (e.g. after compaction)
- The same file is read from multiple paths (e.g. `/tmp/` and `/private/tmp/` on macOS, which are the same location)

To inspect the cache:

```bash
cat /tmp/ollama-vision-fallback.jsonl | jq .
```

## Parallel image processing

Images within a single message are processed **concurrently** via `asyncio.gather`. This means N images complete in roughly the time of one slow VL call, not N sequential calls. Images inside `tool_result` blocks are also parallelised.

Before this change, two images in one request could take ~94s (47s each), exceeding Claude Code's API timeout. With parallel processing, the same request completes in ~47s.

## Ollama model lifecycle

When the VL backend is Ollama, the bridge manages the model lifecycle to avoid GPU blocking:

1. The vision call sends `keep_alive` set to the timeout value (default 120s) as a safety net.
2. After the response returns, `ollama stop <model>` is called via subprocess to **immediately** unload the model and free GPU memory.
3. If `ollama stop` fails for any reason, the `keep_alive` safety net ensures the model unloads after the timeout period (not Ollama's default 5 minutes).

**Cold start note:** `keep_alive: 0` (immediate unload) on a cold model causes a known [Ollama bug](https://github.com/ollama/ollama/issues/14364) where vision models enter a permanent "stopping" state. The `keep_alive` safety net + manual `ollama stop` pattern avoids this.

## Performance notes

- **Image resizing** is done in-memory via Pillow before the VL call
- **Images are processed in parallel** within messages — N images complete in ~1× time, not N× time
- **Cache deduplication** — identical images hit the persistent cache, avoiding any VL call
- **Timeout is per-image**, not per-request — and concurrent processing makes this largely academic
- **Large screenshots** (e.g. Playwright full-page captures) are automatically downsized to prevent payload timeouts

## Cost considerations

| Backend | Cost per image | Latency | Best for |
|---|---|---|---|
| **Kimi K2.6** | Paid API call (~same as any Kimi request) | ~2-5s | Production, highest quality descriptions |
| **Ollama VL** | Free (local compute only) | ~5-15s depending on hardware | Development, privacy-sensitive, cost-conscious |

Using Kimi as a vision fallback means every image turn costs roughly **2x** (one VL call + one main model call). For agents that take frequent screenshots (e.g. Playwright MCP), this adds up. The Ollama path eliminates API costs at the expense of local GPU VRAM.

## Troubleshooting

### "vision_in not supported" even with fallback enabled

Check that `SEVEN_BRIDGES_VISION_FALLBACK_BACKEND` is set correctly with the `backend/model` format:
- ✅ `kimi/kimi-k2-6`
- ❌ `kimi-k2-6` (missing backend prefix)
- ✅ `ollama/gemma4:e4b`

### Timeouts on large images

The default resize (max 1024px, JPEG 85) handles most screenshots. If you still hit timeouts:
- Lower `SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT` won't help — increase it instead
- Or set `SEVEN_BRIDGES_VL_MAX_DIMENSION=512` for more aggressive downsizing
- Or set `SEVEN_BRIDGES_VL_JPEG_QUALITY=70` for smaller payloads

### Ollama model enters "stopping" state and never responds

This is a [known Ollama bug](https://github.com/ollama/ollama/issues/14364) affecting vision models. The bridge avoids `keep_alive: 0` on cold starts to prevent this. If it still occurs, try:
- Restarting Ollama (`ollama serve`)
- Pulling a different VL model (`ollama pull qwen3-vl:8b`)
- Upgrading or downgrading Ollama

### Cache has stale or incorrect descriptions

Delete the cache file and it will rebuild on the next vision call:

```bash
rm /tmp/ollama-vision-fallback.jsonl
```

The cache is per-machine in `/tmp` and is automatically cleaned on reboot.

### Kimi returns 403

The Kimi Code API requires a `claude-code/0.1.0` User-Agent header. The vision fallback module sets this automatically. If you see 403s, verify your `KIMI_CODE_API_KEY` is valid.
