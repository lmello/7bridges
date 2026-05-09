# 7 Bridges of Claude

An [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) proxy that lets **Claude Code** (and other Anthropic clients) talk to multiple LLM backends through clean, native translations.

## Why not LiteLLM?

LiteLLM is great for generic OpenAI-compatible routing, but its internal transformation pipelines are designed for broad compatibility, not precision. When bridging Claude Code to reasoning models like DeepSeek V4 Pro or Kimi K2.6, we kept hitting edge cases — `reasoning_content` handling, cache token accounting, thinking parameter stripping — that required fragile patches to LiteLLM internals.

This project takes the opposite approach: **small, explicit translations** written for each backend, with full control over every field that crosses the boundary.

## Architecture

```
┌─────────────┐     Anthropic API      ┌──────────────┐     Native API      ┌────────────┐
│ Claude Code │ ──── /v1/messages ───▶ │ 7 Bridges    │ ──── /chat/ ─────▶ │ DeepSeek   │
│  (or any    │ ◀───  (responses) ──── │  (proxy)     │ ◀─── completions ──│ Kimi       │
│  Anthropic  │                        │  :4000       │                    │ ...        │
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

| Bridge | Backend | Model | Status |
|---|---|---|---|
| DeepSeek | `api.deepseek.com` | `deepseek-v4-pro`, `deepseek-v4-flash` | Planned |
| Kimi | `api.kimi.com/coding/v1` | `kimi-for-coding` (K2.6) | Planned |

## Project Structure

```
7-bridges-of-claude/
├── src/seven_bridges/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings, env vars, model routing
│   ├── models/
│   │   ├── anthropic.py     # Anthropic Messages API schemas
│   │   └── openai.py        # OpenAI Chat Completions schemas
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract Bridge base class
│   │   ├── deepseek.py      # DeepSeek bridge
│   │   └── kimi.py          # Kimi bridge
│   └── translation/
│       ├── __init__.py
│       ├── request.py       # Anthropic → OpenAI request translation
│       └── response.py      # OpenAI → Anthropic response translation
├── tests/
├── pyproject.toml
└── README.md
```

## Development

```sh
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Run the server:

```sh
uvicorn seven_bridges.main:app --reload --port 4000
```

## License

MIT
