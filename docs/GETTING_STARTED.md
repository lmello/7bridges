# Getting Started with 7 Bridges of Claude

This guide walks you through setting up 7 Bridges from scratch, with detailed instructions for each backend provider and platform.

If you just want the short version, see the [Quick Start](../README.md#quick-start-5-minutes) in the README.

---

## Table of Contents

- [Before You Begin](#before-you-begin)
- [Platform-Specific Setup](#platform-specific-setup)
  - [macOS](#macos)
  - [Linux](#linux)
  - [Windows (WSL2)](#windows-wsl2)
- [Backend Setup Guides](#backend-setup-guides)
  - [DeepSeek](#deepseek)
  - [Kimi (Moonshot)](#kimi-moonshot)
  - [SiliconFlow](#siliconflow)
  - [Fireworks AI](#fireworks-ai)
  - [Ollama (Local)](#ollama-local)
- [Understanding Environment Variables](#understanding-environment-variables)
- [Switching Between Backends](#switching-between-backends)
- [Debug Logging](#debug-logging)
- [Next Steps](#next-steps)

---

## Before You Begin

### What This Project Does

7 Bridges sits between Claude Code and a non-Anthropic LLM. Claude Code thinks it's talking to Anthropic's API, but your requests actually go to DeepSeek, Kimi, Ollama, or another provider.

You need:

1. **This software** running on your computer (port 4001)
2. **An API key** from at least one backend provider (or Ollama running locally)
3. **Claude Code** configured to talk to `localhost:4001` instead of `api.anthropic.com`

### Estimated Time

- **With an API key ready:** 5 minutes
- **Including sign-up and API key creation:** 15–30 minutes

### Estimated Cost

| Path | Upfront Cost | Per-Request Cost |
|---|---|---|
| DeepSeek | Free (trial credits) | ~$0.50–2/million tokens |
| Kimi | Free (trial credits) | ~$1–3/million tokens |
| SiliconFlow | Free tier available | ~$0.30–1/million tokens |
| Fireworks AI | Free (trial credits) | ~$0.50–2/million tokens |
| Ollama | Free | Free (uses your electricity) |

---

## Platform-Specific Setup

### macOS

macOS is the easiest platform for this project. Most tools are one Homebrew command away.

**1. Install Homebrew (if you don't have it):**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**2. Install the required tools:**

```bash
brew install uv git
```

**3. Clone and install:**

```bash
git clone https://github.com/sdkks/7bridges.git
cd 7bridges
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Linux

**Ubuntu/Debian:**

```bash
# Install Python 3.13 (if not already installed)
# Ubuntu 24.04+ has it: sudo apt install python3.13 python3.13-venv
# Older versions: use deadsnakes PPA or pyenv

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install git (usually already present)
sudo apt update && sudo apt install git

# Install direnv (optional but recommended)
sudo apt install direnv

# Clone and install
git clone https://github.com/sdkks/7bridges.git
cd 7bridges
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Fedora/RHEL:**

```bash
sudo dnf install git python3.13 python3.13-devel direnv
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/sdkks/7bridges.git
cd 7bridges
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Arch Linux:**

```bash
sudo pacman -S git python direnv
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/sdkks/7bridges.git
cd 7bridges
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Windows (WSL2)

This project does not run natively on Windows. You must use WSL2 (Windows Subsystem for Linux).

**1. Install WSL2 if you haven't:**

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart your computer when prompted.

**2. Open a WSL2 terminal:**

From the Start menu, search for "Ubuntu" (or your chosen distro) and open it.

**3. Follow the Linux instructions above** inside the WSL2 terminal.

**4. Access from Windows:**

Once the bridge is running in WSL2, it is accessible at `http://localhost:4001` from both WSL2 and Windows. Claude Code running on Windows can connect to it normally.

> **Note:** If you use WSL2, keep all files inside the WSL2 filesystem (`/home/yourname/...`) for better performance. Do not put the project in `/mnt/c/...` (your Windows C: drive) — file operations will be very slow.

---

### Auto-loading with direnv (optional, all platforms)

If you installed `direnv` above, you can use it to automatically load environment variables whenever you `cd` into the project:

```bash
# 1. Add direnv hook to your shell (skip if already done)
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc   # or bash: ~/.bashrc
source ~/.zshrc

# 2. Copy the example env file and fill in your API keys
cp .envrc.example .envrc
# edit .envrc with your keys

# 3. Allow direnv to load it
direnv allow
```

This automatically exports the env vars and adds `.venv/bin` to `PATH` whenever you enter the project directory.

---

## Backend Setup Guides

### DeepSeek

DeepSeek offers a free trial with initial credits. Their v4 models are fast and capable.

**1. Sign up:**

Go to [platform.deepseek.com](https://platform.deepseek.com) and create an account.

**2. Get your API key:**

- Click your profile (top right)
- Go to "API Keys"
- Click "Create API Key"
- Copy the key (starts with `sk-`)

**3. Configure:**

```bash
export DEEPSEEK_API_KEY="sk-your-key-here"
export BRIDGE_API_KEY="ollama"
```

**4. Use in Claude Code:**

```
/model claude-sonnet-4-6    # DeepSeek v4-pro (stronger)
/model claude-haiku-4-5     # DeepSeek v4-flash (faster, cheaper)
```

**Available models:**

| Alias | Actual Model | Context | Best For |
|---|---|---|---|
| `claude-sonnet-4-6` | `deepseek-v4-pro` | 1,048,576 | Complex reasoning, coding |
| `claude-haiku-4-5` | `deepseek-v4-flash` | 1,048,576 | Fast responses, simple tasks |

**Notes:**
- DeepSeek v4 does **not** support vision (images). See [VISION_FALLBACK.md](VISION_FALLBACK.md) for a workaround.
- DeepSeek supports reasoning/thinking blocks and tool use.

---

### Kimi (Moonshot)

Kimi's K2.6 model is excellent for coding and supports vision. The API requires a Kimi Code key.

**1. Sign up:**

Go to [platform.moonshot.cn](https://platform.moonshot.cn) and create an account. The site is in Chinese — use browser translation if needed.

**2. Get your API key:**

- Log in to the dashboard
- Navigate to the API keys section
- Create a new key
- Copy the key

**3. Configure:**

```bash
export KIMI_CODE_API_KEY="your-kimi-key-here"
export BRIDGE_API_KEY="ollama"
```

**4. Use in Claude Code:**

```
/model claude-opus-4-6    # Kimi K2.6
```

**Notes:**
- Kimi K2.6 supports **vision** (image input), reasoning, and tools.
- The context window is 262,144 tokens.
- Reasoning is enabled by default and cannot be disabled.
- The bridge sends a `claude-code/0.1.0` User-Agent header, which is required by the Kimi Code API.

---

### SiliconFlow

SiliconFlow is an aggregator that provides access to multiple models through a single API. They offer a generous free tier.

**1. Sign up:**

Go to [cloud.siliconflow.cn](https://cloud.siliconflow.cn) and create an account.

**2. Get your API key:**

- Go to "API Keys" in the dashboard
- Create a new key
- Copy it

**3. Configure:**

```bash
export SILICONFLOW_API_KEY="your-siliconflow-key-here"
export BRIDGE_API_KEY="ollama"
```

**4. Use in Claude Code:**

```
/model siliconflow-kimi-k2.6       # Kimi K2.6 via SiliconFlow
/model siliconflow-minimax-m2.5    # MiniMax M2.5
/model siliconflow-glm-5.1         # GLM 5.1
```

**Notes:**
- SiliconFlow's free tier has rate limits. Check your dashboard for current limits.
- MiniMax M2.5 and GLM 5.1 do not support vision.
- Kimi K2.6 via SiliconFlow does support vision.

---

### Fireworks AI

Fireworks AI offers fast inference for open models with a trial credit program.

**1. Sign up:**

Go to [fireworks.ai](https://fireworks.ai) and create an account.

**2. Get your API key:**

- Go to "Account" → "API Keys"
- Create a new key
- Copy it

**3. Configure:**

```bash
export FIREWORKSAI_API_KEY="your-fireworks-key-here"
export BRIDGE_API_KEY="ollama"
```

**4. Use in Claude Code:**

```
/model fireworks-kimi-k2p6       # Kimi K2.6 via Fireworks
/model fireworks-minimax-m2p7    # MiniMax M2.7
```

**Notes:**
- Kimi K2.6 via Fireworks accepts the standard Anthropic `thinking` object.
- MiniMax M2.7 uses `reasoning_effort` string instead (`low`/`medium`/`high`).

---

### Ollama (Local)

Ollama lets you run open-weight models entirely on your own hardware. No API keys, no usage costs, works offline.

**Requirements:**
- macOS with Apple Silicon (M1/M2/M3/M4) **or**
- Linux with a CUDA-capable GPU **or**
- Linux with a powerful CPU (slower)
- At least 16 GB RAM for smaller models, 32 GB+ for larger ones

**1. Install Ollama:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Or download from [ollama.com/download](https://ollama.com/download).

**2. Pull models:**

```bash
# Best quality (needs ~32GB RAM)
ollama pull qwen3.6:35b-a3b-coding-nvfp4

# Good balance (needs ~16GB RAM)
ollama pull qwen3.5:9b

# Alternative models
ollama pull gpt-oss:20b
ollama pull gemma4:26b
```

**3. Start Ollama:**

```bash
ollama serve
```

Leave this running in a separate terminal.

**4. Configure the bridge:**

```bash
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
export BRIDGE_API_KEY="ollama"
```

**5. Use in Claude Code:**

```
/model ollama-sonnet      # qwen3.6:35b (best quality)
/model ollama-haiku       # qwen3.5:9b (faster, lighter)
/model ollama-gpt-oss     # gpt-oss:20b
/model ollama-gemma       # gemma4:26b
```

**Troubleshooting Ollama:**

- **"Error: could not connect to ollama"** — Ollama server is not running. Run `ollama serve` in another terminal.
- **Very slow responses** — Your hardware may not have enough RAM. Try a smaller model like `qwen3.5:9b`.
- **Out of memory errors** — Reduce `OLLAMA_*_CONTEXT_WINDOW` values in your `.envrc`.

See [OLLAMA_MODELS.md](OLLAMA_MODELS.md) for detailed per-model notes.

---

## Understanding Environment Variables

Here's what each variable does and whether you need it:

| Variable | Required? | Description |
|---|---|---|
| `BRIDGE_API_KEY` | **Yes** | Password Claude Code sends to authenticate. Can be any string. Must match `ANTHROPIC_API_KEY`. |
| `DEEPSEEK_API_KEY` | Only for DeepSeek | Your DeepSeek API key. |
| `KIMI_CODE_API_KEY` | Only for Kimi | Your Kimi Code API key. |
| `SILICONFLOW_API_KEY` | Only for SiliconFlow | Your SiliconFlow API key. |
| `FIREWORKSAI_API_KEY` | Only for Fireworks | Your Fireworks AI API key. |
| `OLLAMA_HOST` | Only for Ollama | URL of your Ollama server. Default: `http://127.0.0.1:11434` |
| `OLLAMA_SONNET_MODEL` | Only for Ollama | Model name for the `ollama-sonnet` alias. |
| `OLLAMA_HAIKU_MODEL` | Only for Ollama | Model name for the `ollama-haiku` alias. |
| `OLLAMA_SONNET_CONTEXT_WINDOW` | Only for Ollama | Context window for `ollama-sonnet`. Default: `32768`. |
| `OLLAMA_HAIKU_CONTEXT_WINDOW` | Only for Ollama | Context window for `ollama-haiku`. Default: `65536`. |
| `OLLAMA_GPTOSS_CONTEXT_WINDOW` | Only for Ollama | Context window for `ollama-gpt-oss`. Default: `65536`. |
| `OLLAMA_GEMMA_CONTEXT_WINDOW` | Only for Ollama | Context window for `ollama-gemma`. Default: `65536`. |
| `OLLAMA_KEEP_ALIVE` | Only for Ollama | How long to keep model loaded in memory. |
| `SEVEN_BRIDGES_VISION_FALLBACK_ENABLED` | No | Enable experimental vision fallback. See [VISION_FALLBACK.md](VISION_FALLBACK.md). |
| `SEVEN_BRIDGES_VISION_FALLBACK_BACKEND` | No | VL backend for vision fallback. Format: `kimi/kimi-k2-6` or `ollama/gemma4:e4b`. |
| `SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT` | No | Timeout per image in seconds. Default: 120. |
| `SEVEN_BRIDGES_VISION_FALLBACK_OLLAMA_CTX` | No | Context window for Ollama VL calls. Default: 8192. |

### The Two API Keys Explained

There are **two different API keys** in play, which confuses many people:

1. **`BRIDGE_API_KEY`** — This is the password for **your** bridge server. You choose it. Claude Code must send this in every request. It prevents random people from using your bridge if it's exposed to a network.

2. **Backend API keys** (`DEEPSEEK_API_KEY`, `KIMI_CODE_API_KEY`, etc.) — These are the keys you get from the LLM provider. The bridge uses them to talk to DeepSeek, Kimi, etc. You need at least one.

3. **`ANTHROPIC_API_KEY`** — This is set in the environment where you run Claude Code. It **must match** `BRIDGE_API_KEY`. Claude Code sends this value to the bridge as its authentication token.

```
┌─────────────┐          ANTHROPIC_API_KEY          ┌─────────────┐        DEEPSEEK_API_KEY         ┌──────────┐
│ Claude Code │ ────────────────────▶ │ 7 Bridges   │ ─────────────────▶ │ DeepSeek  │
│  (your env)  │    (must match BRIDGE_API_KEY)   │  (your env)  │   (from provider)    │  (provider) │
└─────────────┘                                  └─────────────┘                      └──────────┘
```

---

## Switching Between Backends

You can configure multiple backends at once and switch between them in Claude Code without restarting the bridge.

**1. Set all your API keys:**

```bash
export DEEPSEEK_API_KEY="sk-..."
export KIMI_CODE_API_KEY="sk-..."
export BRIDGE_API_KEY="ollama"
```

**2. Start the bridge once:**

```bash
uvicorn seven_bridges.main:app --reload --port 4001
```

**3. Switch models in Claude Code:**

```
/model claude-sonnet-4-6     # Uses DeepSeek
/model claude-opus-4-6       # Uses Kimi
```

The bridge routes each request to the correct backend based on the model alias.

---

## Debug Logging

Enable debug logging to see every request/response pair:

```bash
make run-debug   # start server with BRIDGE_DEBUG=1
make tail-logs   # tail the latest log with jq formatting
```

Each session gets a `logs/debug/<session_id>.jsonl` file containing:

| Entry | Description |
|---|---|
| `request` | Method, path, headers, parsed request body |
| `stream_body` | Full raw SSE text (for streaming responses) |
| `response` | Status code, duration, headers, body |

**Log truncation:** Large request bodies (over 50 KB) are summarized. Stream bodies are capped to prevent multi-megabyte logs.

Example queries:

```bash
# Read the last 10 entries of the most recent log
cd logs/debug && tail -n 10 $(ls -t *.jsonl | head -1) | jq .

# Filter for just requests
cd logs/debug && cat $(ls -t *.jsonl | head -1) | jq 'select(.type=="request")'

# Filter for errors
cd logs/debug && cat $(ls -t *.jsonl | head -1) | jq 'select(.status_code >= 400)'
```

---

## Usage Dashboard

The bridge includes a real-time usage dashboard that visualizes token consumption, costs, cache effectiveness, error rates, and latency across all backends. The dashboard reads the same JSONL log files described in [USAGE_LOG.md](USAGE_LOG.md) and serves a web UI on port 4002.

### Quick Start

```bash
# Start with PM2
make dashboard

# Or run directly (no PM2)
make dashboard-run
```

Open **http://localhost:4002** in your browser.

### What You See

- **6 stat cards** — total requests, input/output tokens, estimated cost (with per-request average), cache hit rate, error rate
- **3 time-series charts** — requests/hour, tokens/hour, and cost/hour over the last 24 hours, filterable by backend
- **5 sortable tables** — backend breakdown, model breakdown, top sessions, recent errors, recent requests
- **Auto-refresh** — data updates every 10 seconds with a green/red status indicator
- **Backend filter** — pill-style toggle buttons to include/exclude specific backends

### Launch Commands

| Command | Description |
|---|---|
| `make dashboard` | Start dashboard via PM2 |
| `make dashboard-stop` | Stop the dashboard |
| `make dashboard-restart` | Restart the dashboard |
| `make dashboard-logs` | Tail dashboard PM2 logs |
| `make dashboard-run` | Run directly via uvicorn (development) |
| `make start-all` | Start both bridge (4001) and dashboard (4002) |

The dashboard runs as a separate process. Stopping it does not affect the bridge. Starting it does not require restarting the bridge.

For details on the data the dashboard reads and the log format, see [USAGE_LOG.md](USAGE_LOG.md).

---

## Next Steps

- Read the [Architecture Overview](ARCHITECTURE.md) to understand how translation works
- Explore [Vision Fallback](VISION_FALLBACK.md) if you want to use images with non-vision backends
- Check [OLLAMA_MODELS.md](OLLAMA_MODELS.md) for detailed local model information
- Track costs and usage patterns with [Usage Logging](USAGE_LOG.md)
- Understand per-bridge behavior in [BRIDGE_NOTES.md](BRIDGE_NOTES.md)
- Fix common problems with [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Run the test suite: `make check`
