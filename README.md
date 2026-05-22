# 7 Bridges of Claude

An [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) proxy that lets **Claude Code** (and other Anthropic clients) talk to non-Anthropic LLMs through clean, explicit translations.

> **Agentic development guide:** See [`CLAUDE.md`](CLAUDE.md) (also symlinked as [`AGENTS.md`](AGENTS.md)) for conventions on testing integrity, development cadence, backend capability audits, and common pitfalls when working with this codebase.

# What's new?

Added support for SiliconFlow (MiniMax M2.5, Kimi K2.6, GLM 5.1) and Ollama. Some working examples are further down.


https://github.com/user-attachments/assets/8e6fa365-d528-4307-ad36-61fa040a4cc2



## Why I Built This

I wanted to use other models (DeepSeek, Kimi, Ollama, etc.) with Claude Code without fighting LiteLLM every step of the way. With LiteLLM I kept running into:

- **Reasoning/thinking blocks** not being translated correctly — Claude Code expects `thinking` content blocks with signatures; LiteLLM either drops them or mangles the format
- **Cache token accounting** being inconsistent — `cache_read_input_tokens` and `cache_creation_input_tokens` would be missing or wrong
- **Streaming SSE** breaking on edge cases — empty deltas, usage-only chunks, or `data:` lines without spaces would cause silent failures
- **Too many moving parts** — LiteLLM's broad-compatibility approach means dozens of internal transformation pipelines, any of which can break for Anthropic-specific features

This project takes the opposite approach: **small, explicit, per-backend translations** where every field that crosses the boundary is deliberately mapped and tested.

## Vision

Every non-Anthropic model speaks the **Anthropic Messages API** (`/v1/messages`). The bridge is a translation layer — nothing more. You point Claude Code at `localhost:4001`, pick a model alias like `claude-opus-4-6`, and the bridge forwards your request to the actual upstream (Kimi, DeepSeek, etc.), then translates the response back into native Anthropic format including:

- `thinking` blocks with reasoning content
- `tool_use` / `tool_result` blocks
- `image` input blocks (where upstream supports vision)
- Streaming SSE events (`message_start`, `content_block_delta`, `message_stop`)
- Proper `usage` with cache accounting

## Architecture

```
┌─────────────┐     Anthropic API      ┌──────────────┐     Native API      ┌────────────┐
│ Claude Code │ ──── /v1/messages ───▶ │ 7 Bridges    │ ──── /chat/ ─────▶ │ DeepSeek   │
│  (or any    │ ◀───  (responses) ──── │  (proxy)     │ ◀─── completions ──│ Kimi       │
│  Anthropic  │                        │  :4001       │                    │ ...        │
│  client)    │                        │              │                    │            │
└─────────────┘                        └──────────────┘                    └────────────┘
```

Each backend is a "bridge":
- Receives Anthropic-format `MessagesRequest`
- Translates to the backend's native request format
- Forwards the request via HTTP
- Translates the native response back to Anthropic-format `MessagesResponse`
- Handles streaming SSE translation chunk-by-chunk

## Bridges

| Bridge | Backend | Model | Vision | Reasoning | Tools | Status |
|---|---|---|---|---|---|---|
| DeepSeek | `api.deepseek.com` | `deepseek-v4-pro` (Sonnet), `deepseek-v4-flash` (Haiku) | ❌ | ✅ | ✅ | Live |
| Kimi | `api.kimi.com/coding/v1` | `kimi-for-coding` (K2.6) | ✅ | ✅ | ✅ | Live |
| Ollama | `localhost:11434` | Configurable via env vars | ✅ | ✅ | ✅ | Live |
| SiliconFlow | `api.siliconflow.com/v1` | MiniMax M2.5, GLM 5.1 | ❌ | ✅ | ✅ | Live |
| SiliconFlow | `api.siliconflow.com/v1` | Kimi K2.6 | ✅ | ✅ | ✅ | Live |

> **Note on vision/image support:** DeepSeek v4 does not natively support image input. By default, image requests to DeepSeek receive a **soft 200 rejection** with guidance to use OCR/DOM fallbacks instead of a fatal 400 error. For full vision support, you can either use the **Kimi bridge** (`claude-opus-4-6` or `claude-opus-4-7`) which maps to Kimi K2.6, or enable the experimental **vision fallback** feature that routes images to a separate VL backend (Kimi or Ollama) and feeds the text description back to the blind model. See [docs/VISION_FALLBACK.md](docs/VISION_FALLBACK.md).

### Model Aliases

| Alias | Backend | Model | Context | Max Output |
|---|---|---|---|---|
| `claude-sonnet-4-6` | DeepSeek | `deepseek-v4-pro` | 1,048,576 | 393,216 |
| `claude-haiku-4-5` | DeepSeek | `deepseek-v4-flash` | 1,048,576 | 393,216 |
| `claude-opus-4-6` | Kimi | `kimi-for-coding` | 262,144 | 32,768 |
| `claude-haiku-4-5-20251001` | DeepSeek | `deepseek-v4-flash` | 1,048,576 | 393,216 |
| `ollama-sonnet` | Ollama | `qwen3.6:35b-a3b-coding-nvfp4` | 32,768 | 8,192 |
| `ollama-haiku` | Ollama | `qwen3.5:9b` | 65,536 | 8,192 |
| `ollama-gpt-oss` | Ollama | `gpt-oss:20b` | 65,536 | 8,192 |
| `ollama-gemma` | Ollama | `gemma4:26b` | 65,536 | 8,192 |
| `siliconflow-minimax-m2.5` | SiliconFlow | `MiniMaxAI/MiniMax-M2.5` | 196,608 | 196,608 |
| `siliconflow-kimi-k2.6` | SiliconFlow | `moonshotai/Kimi-K2.6` | 262,144 | 262,144 |
| `siliconflow-glm-5.1` | SiliconFlow | `zai-org/GLM-5.1` | 200,000 | 131,072 |

## Ollama Setup

The Ollama bridge talks to your local Ollama instance via the [ollama-python SDK](https://github.com/ollama/ollama-python). The aliases `ollama-sonnet`, `ollama-haiku`, `ollama-gpt-oss`, and `ollama-gemma` map to open-weight models that serve as rough local analogues for the Anthropic model tiers — they trade some capability for zero-cost, offline, private inference. Models are configured through environment variables in `.envrc`:

```sh
export OLLAMA_HOST="http://127.0.0.1:11434"
export OLLAMA_SONNET_MODEL="qwen3.6:35b-a3b-coding-nvfp4"
export OLLAMA_SONNET_CONTEXT_WINDOW=32768
export OLLAMA_HAIKU_MODEL="qwen3.5:9b"
export OLLAMA_HAIKU_CONTEXT_WINDOW=65536
export OLLAMA_GPTOSS_MODEL="gpt-oss:20b"
export OLLAMA_GPTOSS_CONTEXT_WINDOW=65536
export OLLAMA_GEMMA_MODEL="gemma4:26b"
export OLLAMA_GEMMA_CONTEXT_WINDOW=65536
export OLLAMA_KEEP_ALIVE="300s"
```

**Pull the models you want before using them:**

```sh
ollama pull qwen3.6:35b-a3b-coding-nvfp4
ollama pull qwen3.5:9b
ollama pull gpt-oss:20b
ollama pull gemma4:26b
```

### Using Ollama models in Claude Code

Ollama models use the aliases `ollama-sonnet`, `ollama-haiku`, `ollama-gpt-oss`, and `ollama-gemma`. They are **not** listed in the default `/model` picker (Claude Code filters to known Anthropic aliases). Switch to them explicitly:

```
/model ollama-sonnet
/model ollama-haiku
/model ollama-gpt-oss
/model ollama-gemma
```

> **Tip:** Bump the context window in `.envrc` if your hardware allows it. `OLLAMA_SONNET_CONTEXT_WINDOW` and `OLLAMA_HAIKU_CONTEXT_WINDOW` control the `num_ctx` parameter passed to Ollama. These defaults were tested on an Apple Silicon M2 Pro with 32 GB unified memory — your own limits will vary with hardware and the models you choose. Measure the tradeoffs and adjust via env vars.

> **Known quirk:** `ollama-gpt-oss` has a ~50% failure rate on first-time `Write` tool calls — the model sometimes emits the tool call with incomplete parameters. Subsequent retries almost always succeed as the model corrects itself.

See [`docs/OLLAMA_MODELS.md`](docs/OLLAMA_MODELS.md) for full capabilities, architecture details, and per-model notes.

## Setup

```sh
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Set your upstream API keys:

```sh
export DEEPSEEK_API_KEY="sk-..."
export KIMI_CODE_API_KEY="sk-..."
export SILICONFLOW_API_KEY="sk-..."
export BRIDGE_API_KEY="ollama"  # or whatever you want Claude Code to send
```

**Auto-loading with direnv** (optional):

```sh
cp .envrc.example .envrc
# edit .envrc and fill in your API keys
direnv allow
```

This automatically exports the env vars and adds `.venv/bin` to `PATH` whenever you `cd` into the project.

Run via PM2 (production) or directly (development):

```sh
# Production
make start

# Development with debug logging
make run-debug

# Development (basic)
uvicorn seven_bridges.main:app --reload --port 4001
```

Point Claude Code at the bridge:

```sh
export ANTHROPIC_BASE_URL="http://localhost:4001"
export ANTHROPIC_API_KEY="ollama"
```

## Usage

List available models:

```sh
curl http://localhost:4001/v1/models
```

Send a message (non-streaming):

```sh
curl -X POST http://localhost:4001/v1/messages \
  -H "x-api-key: ollama" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

Send a message (streaming):

```sh
curl -N -X POST http://localhost:4001/v1/messages \
  -H "x-api-key: ollama" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100,
    "stream": true
  }'
```

Count tokens (local estimation):

```sh
curl -X POST http://localhost:4001/v1/messages/count_tokens \
  -H "x-api-key: ollama" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Project Structure

```
7-bridges-of-claude/
├── src/seven_bridges/
│   ├── main.py              # FastAPI app & routing
│   ├── config.py            # Settings, env vars, model routing
│   ├── debug.py             # Request/response JSONL logging
│   ├── models/
│   │   ├── anthropic.py     # Anthropic Messages API Pydantic models
│   │   └── openai.py        # OpenAI Chat Completions Pydantic models
│   ├── backends/
│   │   ├── base.py          # Abstract Bridge base class + capabilities
│   │   ├── deepseek.py      # DeepSeek bridge
│   │   ├── kimi.py          # Kimi bridge
│   │   ├── ollama.py        # Ollama bridge
│   │   └── siliconflow.py   # SiliconFlow bridge
│   └── translation/
│       ├── request.py       # Anthropic → OpenAI request translation
│       ├── response.py      # OpenAI → Anthropic response translation
│       └── stream.py        # OpenAI SSE → Anthropic SSE streaming
├── tests/
│   ├── test_translation.py      # Unit tests for request/response conversion
│   ├── test_streaming.py        # Unit tests for SSE event generation
│   ├── test_e2e.py              # E2E tests with mocked upstreams
│   ├── test_smoke.py            # Smoke tests for API basics
│   ├── test_smoke_streaming.py  # Live streaming smoke tests (hits real APIs)
│   ├── test_debug.py            # Debug middleware tests
│   └── agent-inference/         # Integration tests against live upstreams
│       ├── fixtures.json        # 5 test scenarios with evaluation criteria
│       ├── test_agent_inference.py  # Parametrized: 3 models × 5 fixtures
│       └── README.md            # How the evaluation framework works
├── docs/api-schemas/        # Reference OpenAPI specs
├── Makefile                 # Test, lint, format targets
└── ecosystem.config.js      # PM2 process config
```

## Debug Logging

Every request/response pair is written to `logs/debug/<session_id>.jsonl` when `BRIDGE_DEBUG=1` is set.

```sh
# Run the server with debug logging enabled
make run-debug

# In another terminal, tail the latest log with jq formatting
make tail-logs
```

Each JSONL file contains:

| Entry | Description |
|---|---|
| `request` | Method, path, headers, parsed request body |
| `stream_body` | Full raw SSE text (for streaming responses) |
| `response` | Status code, duration, headers, body (or `<streaming_response: N bytes>`) |

**Log truncation:** Large request bodies (over 50 KB) are summarized instead of logged verbatim. Stream bodies are also capped. This prevents multi-megabyte debug logs when sending large files.

Example — read the last 10 entries of the most recent log:

```sh
cd logs/debug && tail -n 10 $(ls -t *.jsonl | head -1) | jq .
```

Filter for just the requests:

```sh
cd logs/debug && cat $(ls -t *.jsonl | head -1) | jq 'select(.type=="request")'
```

Filter for errors only:

```sh
cd logs/debug && cat $(ls -t *.jsonl | head -1) | jq 'select(.status_code >= 400)'
```

## Development

Run all checks:

```sh
make check       # lint + test
make test-cov    # tests with coverage report
```

Individual targets:

```sh
make test-unit   # translation + streaming unit tests
make test-e2e    # mocked upstream e2e tests
make test-smoke  # API smoke tests
make lint        # ruff + mypy
make format      # ruff format
```

Pre-commit hooks (runs on every commit):

```sh
pre-commit install
```

Includes: gitleaks, ruff check, ruff format, mypy, pytest with 80% coverage gate.

## Tests

113 tests, ~82% coverage:

- **Unit**: Request/response field mapping, content block conversion, streaming event generation
- **E2E**: Full HTTP round-trips with mocked DeepSeek, Kimi, SiliconFlow, and Ollama APIs using `respx`
- **Smoke**: Health, auth, model listing, validation errors
- **Debug**: Middleware request/response capture
- **Vision fallback**: Image description extraction and VL round-trips

## License

MIT
