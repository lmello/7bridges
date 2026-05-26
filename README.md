# 7 Bridges of Claude

An [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) proxy that lets **Claude Code** (and other Anthropic clients) talk to non-Anthropic LLMs through clean, explicit translations.

> **Agentic development guide:** See [`CLAUDE.md`](CLAUDE.md) (also symlinked as [`AGENTS.md`](AGENTS.md)) for conventions on testing integrity, development cadence, backend capability audits, and common pitfalls when working with this codebase.

## What's New?

Added support for **SiliconFlow** (MiniMax M2.5, Kimi K2.6, GLM 5.1), **Fireworks AI** (Kimi K2.6, MiniMax M2.7), and **Ollama**.

---

## Table of Contents

- [Why I Built This](#why-i-built-this)
- [What You Need](#what-you-need)
- [Quick Start (5 Minutes)](#quick-start-5-minutes)
- [Pick a Model](#pick-a-model)
- [Run It](#run-it)
- [Usage Examples](#usage-examples)
- [Logging](#logging)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [License](#license)

---

## Why I Built This

I wanted to use other models (DeepSeek, Kimi, Ollama, etc.) with Claude Code without fighting LiteLLM every step of the way. With LiteLLM I kept running into:

- **Reasoning/thinking blocks** not being translated correctly
- **Cache token accounting** being inconsistent
- **Streaming SSE** breaking on edge cases
- **Too many moving parts** — dozens of internal transformation pipelines

This project takes the opposite approach: **small, explicit, per-backend translations** where every field that crosses the boundary is deliberately mapped and tested.

## Vision

Every non-Anthropic model speaks the **Anthropic Messages API** (`/v1/messages`). You point Claude Code at `localhost:4001`, pick a model alias like `claude-opus-4-6`, and the bridge forwards your request to the actual upstream, then translates the response back into native Anthropic format.

```
├───────────┐     Anthropic API      ├───────────┐     Native API      ├────────┐
│ Claude Code │ ──── /v1/messages ───▶ │ 7 Bridges    │ ──── /chat/ ────▶ │ DeepSeek   │
│  (or any    │ ◀─── (responses) ────│  (proxy)     │ ◀─── completions ──│ Kimi       │
│  Anthropic  │                        │  :4001       │                    │ Ollama     │
│  client)    │                        │              │                    │ ...        │
└───────────┘                        └───────────┘                    └────────┘
```

---

## What You Need

| Requirement | What It Is | How to Check |
|---|---|---|
| **Python 3.13+** | The programming language this tool is written in | `python3 --version` |
| **uv** | A fast Python package manager | `uv --version` |
| **Git** | To download this project | `git --version` |
| **An API key** | From at least one backend provider | See below |

**You do NOT need all of these.** Pick one backend and get one API key. Many are free to try with credit.

> **Windows users:** This project runs on Linux and macOS. Use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) and follow the Linux instructions.

---

## Quick Start (5 Minutes)

If you already have `uv` installed and an API key ready:

```bash
# 1. Download the project
git clone https://github.com/sdkks/7bridges.git
cd 7bridges

# 2. Create the Python environment and install dependencies
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"

# 3. Set your API key (example: DeepSeek)
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
export BRIDGE_API_KEY="ollama"  # this is the password Claude Code will use

# 4. Start the server
uvicorn seven_bridges.main:app --reload --port 4001
```

In another terminal:

```bash
# 5. Point Claude Code at the bridge
export ANTHROPIC_BASE_URL="http://localhost:4001"
export ANTHROPIC_API_KEY="ollama"
claude
```

Then inside Claude Code, pick a model:

```
/model claude-sonnet-4-6
```

Done! To verify it's working, try:

```bash
curl http://localhost:4001/v1/models
curl -X POST http://localhost:4001/v1/messages \
  -H "x-api-key: ollama" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}'
```

> **New here?** See [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) for a full step-by-step walkthrough with platform-specific instructions (macOS, Linux, WSL2), per-backend setup guides, and environment variable explanations.

---

## Pick a Model

**New to this?** Start here:

| If you want... | Use this alias | Backend | Cost | Notes |
|---|---|---|---|---|
| Best overall quality | `claude-opus-4-6` | Kimi K2.6 | Paid | Excellent reasoning, vision, tools. 262K context. |
| Fast and cheap | `claude-haiku-4-5` | DeepSeek v4-flash | Paid | Very fast, 1M context, great for quick tasks. |
| Good balance | `claude-sonnet-4-6` | DeepSeek v4-pro | Paid | Strong reasoning, 1M context, cheaper than Kimi. |
| Completely free | `ollama-sonnet` | Local Qwen 3.6 | Free | Runs on your computer. Needs ~32GB RAM. |
| Free, lighter | `ollama-haiku` | Local Qwen 3.5 | Free | Runs on your computer. Needs ~16GB RAM. |

**Full model alias reference:**

| Alias | Backend | Actual Model | Context | Max Output |
|---|---|---|---|---|
| `claude-sonnet-4-6` | DeepSeek | `deepseek-v4-pro` | 1,048,576 | 393,216 |
| `claude-haiku-4-5` | DeepSeek | `deepseek-v4-flash` | 1,048,576 | 393,216 |
| `claude-opus-4-6` | Kimi | `kimi-for-coding` | 262,144 | 32,768 |
| `claude-opus-4-7` | Kimi | `kimi-for-coding` | 262,144 | 32,768 |
| `ollama-sonnet` | Ollama | `qwen3.6:35b-a3b-coding-nvfp4` | 32,768 | 8,192 |
| `ollama-haiku` | Ollama | `qwen3.5:9b` | 65,536 | 8,192 |
| `ollama-gpt-oss` | Ollama | `gpt-oss:20b` | 65,536 | 8,192 |
| `ollama-gemma` | Ollama | `gemma4:26b` | 65,536 | 8,192 |
| `siliconflow-minimax-m2.5` | SiliconFlow | `MiniMaxAI/MiniMax-M2.5` | 196,608 | 196,608 |
| `siliconflow-kimi-k2.6` | SiliconFlow | `moonshotai/Kimi-K2.6` | 262,144 | 262,144 |
| `siliconflow-glm-5.1` | SiliconFlow | `zai-org/GLM-5.1` | 200,000 | 131,072 |
| `fireworks-kimi-k2p6` | Fireworks AI | `accounts/fireworks/models/kimi-k2p6` | 262,144 | 262,144 |
| `fireworks-minimax-m2p7` | Fireworks AI | `accounts/fireworks/models/minimax-m2p7` | 204,800 | 131,072 |

> **Per-bridge details:** Thinking/reasoning behavior, vision support, and known quirks for each backend are documented in [`docs/BRIDGE_NOTES.md`](docs/BRIDGE_NOTES.md).

---

## Run It

| Command | When to Use |
|---|---|
| `uvicorn seven_bridges.main:app --reload --port 4001` | Development — auto-reloads on code changes |
| `make run-debug` | Debugging — logs every request/response to `logs/debug/` |
| `make start` | Production — uses PM2, restarts on crash |
| `make stop` | Stop the PM2 process |
| `make logs` | Tail PM2 logs in real time |

### Ollama (Local & Free)

The Ollama bridge runs models entirely on your computer — no API keys, no costs, works offline. Install Ollama, pull a model, run `ollama serve`, and configure a few env vars. See [`docs/OLLAMA_MODELS.md`](docs/OLLAMA_MODELS.md) for full setup and per-model notes.

---

## Usage Examples

### List Available Models

```bash
curl http://localhost:4001/v1/models
```

### Send a Message

```bash
curl -X POST http://localhost:4001/v1/messages \
  -H "x-api-key: ollama" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

### Streaming

```bash
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

### Count Tokens

```bash
curl -X POST http://localhost:4001/v1/messages/count_tokens \
  -H "x-api-key: ollama" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

---

## Logging

### Debug Logging

Every request/response is logged to `logs/debug/<session_id>.jsonl` when `BRIDGE_DEBUG=1` is set:

```bash
make run-debug    # start with debug logging
make tail-logs    # tail the latest log with jq formatting
```

For log structure, filtering examples, and log rotation, see [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

### Usage Logging

Every successful chat completion is automatically logged to `logs/usage.jsonl` with token counts and request metadata. Always on, no config needed.

```bash
cd logs && tail -n 5 usage.jsonl | jq .
```

For query examples, log rotation, and the full field reference, see [`docs/USAGE_LOG.md`](docs/USAGE_LOG.md).

---

## Troubleshooting

### "command not found: uv"

`uv` is not installed. See [GETTING_STARTED.md](docs/GETTING_STARTED.md#platform-specific-setup) for install instructions.

### "Failed to connect" on port 4001

The bridge server is not running. Start it:

```bash
uvicorn seven_bridges.main:app --reload --port 4001
```

### "401 Unauthorized"

`ANTHROPIC_API_KEY` (in Claude Code's env) must exactly match `BRIDGE_API_KEY` (in the bridge's env).

### Claude Code still talks to Anthropic

Claude Code caches the base URL. After changing `ANTHROPIC_BASE_URL`, fully quit and restart:

```bash
/quit   # inside Claude Code
# then in your terminal:
export ANTHROPIC_BASE_URL="http://localhost:4001"
claude
```

> **More issues?** See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) for the full guide.

---

## Development

```bash
make check       # lint + test
make test-cov    # tests with coverage report
make lint        # ruff + mypy
make format      # ruff format
```

Pre-commit hooks: `pre-commit install`

156 tests, ~82% coverage. See [`CLAUDE.md`](CLAUDE.md) for development conventions.

---

## Architecture

For a deep dive into the translation pipeline, content block mapping, streaming state machine, and how to add a new backend, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Brief overview:

```
src/seven_bridges/
├── main.py              # FastAPI app & routing
├── config.py            # Settings, env vars, model routing
├── debug.py             # Request/response JSONL logging
├── usage_log.py         # Per-request token usage logging
├── models/
│   ├── anthropic.py     # Anthropic Messages API Pydantic models
│   └── openai.py        # OpenAI Chat Completions Pydantic models
├── backends/
│   ├── base.py          # Abstract Bridge base class + capabilities
│   ├── deepseek.py      # DeepSeek bridge
│   ├── kimi.py          # Kimi bridge
│   ├── fireworks.py     # Fireworks AI bridge
│   ├── ollama.py        # Ollama bridge
│   └── siliconflow.py   # SiliconFlow bridge
└── translation/
    ├── request.py       # Anthropic -> OpenAI request translation
    ├── response.py      # OpenAI -> Anthropic response translation
    └── stream.py        # OpenAI SSE -> Anthropic SSE streaming
```

---

## Project Structure

```
7-bridges-of-claude/
├── src/seven_bridges/         # Main source code
├── tests/                     # All tests
│   ├── test_translation.py    # Unit tests for request/response conversion
│   ├── test_streaming.py      # Unit tests for SSE event generation
│   ├── test_e2e.py            # E2E tests with mocked upstreams
│   ├── test_smoke.py          # Smoke tests for API basics
│   ├── test_debug.py          # Debug middleware tests
│   ├── test_usage_log.py      # Usage logging tests
│   └── agent-inference/       # Integration tests against live upstreams
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md        # Technical deep dive
│   ├── GETTING_STARTED.md     # Detailed platform and backend guides
│   ├── BRIDGE_NOTES.md        # Per-bridge behavior details
│   ├── USAGE_LOG.md           # Usage logging reference and queries
│   ├── TROUBLESHOOTING.md     # Full troubleshooting guide
│   ├── VISION_FALLBACK.md     # Experimental vision feature
│   ├── OLLAMA_MODELS.md       # Ollama model reference
│   └── api-schemas/           # API schema references
├── Makefile                   # Common commands (test, lint, start, etc.)
├── pyproject.toml             # Python project config & dependencies
├── ecosystem.config.js        # PM2 process config
├── .envrc.example             # Example environment variables
└── README.md                  # This file
```

---

## License

MIT
