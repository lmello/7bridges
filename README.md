# 7 Bridges of Claude

An [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) proxy that lets **Claude Code** (and other Anthropic clients) talk to non-Anthropic LLMs through clean, explicit translations.

## Why I Built This

I wanted to use other models (DeepSeek, Kimi, etc.) with Claude Code without fighting LiteLLM every step of the way. With LiteLLM I kept running into:

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
export BRIDGE_API_KEY="ollama"  # or whatever you want Claude Code to send
```

Run via PM2 (production) or directly (development):

```sh
# Production
make start

# Development
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
│   │   └── kimi.py          # Kimi bridge
│   └── translation/
│       ├── request.py       # Anthropic → OpenAI request translation
│       ├── response.py      # OpenAI → Anthropic response translation
│       └── stream.py        # OpenAI SSE → Anthropic SSE streaming
├── tests/
│   ├── test_translation.py  # Unit tests for request/response conversion
│   ├── test_streaming.py    # Unit tests for SSE event generation
│   ├── test_e2e.py          # E2E tests with mocked upstreams
│   ├── test_smoke.py        # Smoke tests for API basics
│   └── test_debug.py        # Debug middleware tests
├── docs/api-schemas/        # Reference OpenAPI specs
├── Makefile                 # Test, lint, format targets
└── ecosystem.config.js      # PM2 process config
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

50 tests, ~92% coverage:

- **Unit**: Request/response field mapping, content block conversion, streaming event generation
- **E2E**: Full HTTP round-trips with mocked DeepSeek and Kimi APIs using `respx`
- **Smoke**: Health, auth, model listing, validation errors
- **Debug**: Middleware request/response capture

## License

MIT
