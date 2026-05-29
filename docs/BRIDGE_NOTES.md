# Per-Bridge Notes

Detailed behavior notes for each backend bridge. For setup instructions, see [GETTING_STARTED.md](GETTING_STARTED.md).

---

## Kimi (`claude-opus-4-6`, `claude-opus-4-7`)

- **Thinking / reasoning:** Enabled by default. Kimi does not support `budget_tokens` or `reasoning_effort` — there is no way to control reasoning depth.
- **Context window:** The bridge advertises `262,144` tokens. Kimi K2.6 genuinely supports this. However, Claude Code uses its own hardcoded model catalog for known Anthropic aliases and may assume a larger context window (200K or 1M for Opus-tier models) for session compaction decisions. If Claude Code accumulates a context larger than 256K tokens before compacting, Kimi will reject the request.
- **Vision:** Full image input support.
- **Tools:** Full tool use support.
- **Video:** Supported via the bridge's video handling.

---

## DeepSeek (`claude-sonnet-4-6`, `claude-haiku-4-5`)

- **Thinking / reasoning:** The bridge maps Anthropic `thinking.type` to DeepSeek's `thinking` object, and `output_config.effort` to DeepSeek's `reasoning_effort`.
- **Vision:** DeepSeek v4 does **not** support image input. By default, image requests to DeepSeek receive a soft 200 rejection with guidance to use OCR/DOM fallbacks. For full vision support, use the Kimi bridge (`claude-opus-4-6` or `claude-opus-4-7`). See [VISION_FALLBACK.md](VISION_FALLBACK.md) for an experimental alternative.
- **Context window:** 1,048,576 tokens.
- **Max output:** 393,216 tokens.

---

## SiliconFlow (`siliconflow-kimi-k2.6`, `siliconflow-minimax-m2.5`, `siliconflow-glm-5.1`)

- **Thinking / reasoning:** The bridge maps Anthropic `thinking.type` to `enable_thinking` (bool) and `output_config.effort` to a token budget (`thinking_budget`). Budget mapping:

  | `effort` | `thinking_budget` |
  |---|---|
  | `low` | 4096 |
  | `medium` | 8192 |
  | `high` | 16384 |
  | `xhigh` | 24576 |
  | `max` | 32768 |

- **Vision:** Kimi K2.6 via SiliconFlow supports vision. MiniMax M2.5 and GLM 5.1 do not.
- **Free tier:** Has rate limits. Check your dashboard for current limits.

---

## Fireworks AI (`fireworks-kimi-k2p6`, `fireworks-minimax-m2p7`)

- **Thinking / reasoning:**
  - Kimi K2.6 via Fireworks accepts the standard Anthropic-compatible `thinking` object with `type` and `budget_tokens`.
  - MiniMax M2.7 only accepts `reasoning_effort` string (`low` / `medium` / `high`); the bridge converts accordingly.
- **Vision:** Kimi K2.6 supports vision. MiniMax M2.7 does not.

---

## Ollama (`ollama-sonnet`, `ollama-haiku`, `ollama-gpt-oss`, `ollama-gemma`)

- Runs entirely locally — no API keys, no usage costs, works offline after model download.
- Context windows are configurable via `OLLAMA_*_CONTEXT_WINDOW` environment variables. These control the `num_ctx` parameter passed to Ollama.
- Default context windows were tested on an Apple Silicon M2 Pro with 32 GB unified memory — your limits will vary based on available RAM.

### Known Quirks

- **`ollama-gpt-oss`** has a ~50% failure rate on first-time `Write` tool calls — the model sometimes emits the tool call with incomplete parameters. Subsequent retries almost always succeed.

See [OLLAMA_MODELS.md](OLLAMA_MODELS.md) for full capabilities, architecture details, and per-model notes.

---

## Xiaomi MiMo (`mimo-v2.5-pro`, `mimo-v2.5`)

- **Thinking / reasoning:** MiMo returns `reasoning_content` natively in both streaming and non-streaming responses. The bridge maps this to Anthropic `thinking` blocks. You can control reasoning through:
  - `thinking.type`: `"enabled"` / `"adaptive"` → reasoning on; `"disabled"` → reasoning off. Both map to MiMo's `thinking` object.
  - `thinking.budget_tokens`: passed through to MiMo's `thinking.budget_tokens` for token-level control.
  - `output_config.effort`: maps to MiMo's `reasoning_effort`. MiMo only supports `low` / `medium` / `high` — `xhigh` and `max` are silently clamped to `high` to avoid upstream rejection.
  - If neither `thinking` nor `output_config` is specified, MiMo defaults to reasoning on (it always reasons unless explicitly disabled).
- **Prompt caching:** Enabled via `prompt_cache_key` forwarded from `x-claude-code-session-id`. Cache hits appear in `usage.cache_read_input_tokens`. The cache threshold is approximately 1000+ tokens — prefixes smaller than this will not trigger caching. Cache tokens are reported inside `prompt_tokens_details.cached_tokens` in the upstream response, which the bridge extracts and maps to Anthropic's `cache_read_input_tokens`.
- **Vision:** Full multimodal support — native image input via `image_url` blocks.
- **Tools:** Full tool use support.
- **Context window:** 1,000,000 tokens.
- **Auth:** Uses the `api-key` header (not `Authorization: Bearer`). Token plan API keys are created in the MiMo console under Subscription Details and use the `tp-` prefix. The bridge points to the token plan endpoint (`token-plan-sgp.xiaomimimo.com/v1`).
- **Streaming:** MiMo sends `reasoning_content` deltas interleaved with `content` deltas. The bridge's streaming translator handles this by opening a thinking block first, then transitioning to a text block when content arrives.
