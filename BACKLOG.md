# Backlog

Deferred items and known gaps — not blocking, but tracked for visibility.

## Content Block Types

Anthropic has added several content block types since 7 Bridges was built.
We model the ones Claude Code actively uses; the rest are documented in
[docs/api-schemas/anthropic-content-blocks.md](docs/api-schemas/anthropic-content-blocks.md).

**Missing request-side types** (will add when Claude Code starts using them):

- `server_tool_use` — server-initiated tool calls
- `search_result` — search result content
- `web_search_tool_result` — web search tool output
- `web_fetch_tool_result` — web fetch tool output
- `code_execution_tool_result` — code execution output
- `bash_code_execution_tool_result` — bash execution output
- `text_editor_code_execution_tool_result` — text editor execution output
- `tool_search_tool_result` — tool search result
- `container_upload` — container upload block
- `mid_conversation_system` — system message mid-conversation

Each missing type would cause a 400 validation error if Claude Code sends it.
When that happens, add the stub model (thin Pydantic class with `type` literal
and `source`/`content` fields), a text placeholder in the OpenAI translation
path, and tests. Passthrough bridges forward them natively.

## Deferred Features

- **Ollama Anthropic endpoint investigation** — Does Ollama support an
  Anthropic-compatible API? Would simplify that bridge considerably.

- **`cache_control` → DeepSeek-specific format** — DeepSeek's automatic prefix
  detection works well enough (97% hit rate) without explicit markers.
  Low priority.

## Zero-Downtime Restart Architecture

When the bridge restarts (deploy, config change), active Claude Code sessions
are interrupted. The goal is a TCP-level proxy that stays on port 4001 while
the actual uvicorn instance restarts behind it, so clients reconnect
transparently.

### Design

Two-layer PM2 setup:

**Layer 1 — TCP proxy** (`7bridges-proxy`):
- Minimal Python TCP proxy process, stays alive on port 4001
- Forwards to the current uvicorn backend port (e.g. 40010)
- Only restarts if the machine reboots; never restarts during deploys
- Written in stdlib Python, ships in the repo — no external dependencies like socat

**Layer 2 — Uvicorn instances** (`7bridges-cluster`):
- One or more uvicorn instances on backend ports (40010, 40011, ...)
- Managed by PM2 cluster/fork mode
- `SO_REUSEADDR` on backend ports allows the new instance to bind while
  the old one is still draining in-flight streaming SSE responses
- On `pm2 restart` of an instance: proxy keeps port 4001 alive,
  stops forwarding to the restarting backend, new instance starts,
  proxy forwards to new instance

### Implementation

The TCP proxy (~50 lines, stdlib Python) lives at
`src/seven_bridges/proxy.py`. It:
- Binds `127.0.0.1:4001` with `SO_REUSEADDR`
- Accepts connections and relays bidirectionally to the current backend port
- Has a config-reload signal (SIGHUP) so it can flip to a new backend port
  without restarting the proxy itself

The PM2 ecosystem config (`ecosystem.config.js`) runs both layers:
- `7bridges-proxy`: single Python process, `exec_mode: fork`, long `kill_timeout`
- `7bridges-cluster`: uvicorn instances on backend ports

### Alternatives considered

- **`socat` as front-end relay** — works but is not pre-installed on macOS,
  often blocked/removed by IT departments. Not portable.
- **`pfctl` packet filter** — requires sudo, complex config. Too heavy.
- **Nginx stream block** — works well but adds an external dependency.
- **Two-PM2-layer with custom LB** — requires implementing in-flight request
  tracking and graceful draining in the LB itself. Non-trivial to get right
  (SSE streaming lifetimes, HTTP keep-alive, connection state).

The stdlib proxy is the most portable and self-contained option.

### Status

Not implemented. The proxy is straightforward to build; the main open question
is whether uvicorn/FastAPI's graceful shutdown (`SIGTERM` → finish in-flight
→ exit) is fast enough for the SSE streaming responses that 7bridges handles,
or if a longer `kill_timeout` is needed to avoid killing mid-stream.
