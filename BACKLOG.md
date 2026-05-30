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

- **MiniMax Anthropic passthrough bridge** — MiniMax has a native Anthropic
  endpoint (`api.minimax.io/anthropic`) with `cache_control` support. The
  `is_passthrough` pattern is established; just needs a bridge class and model
  routes. Hold until someone asks for it.

- **Ollama Anthropic endpoint investigation** — Does Ollama support an
  Anthropic-compatible API? Would simplify that bridge considerably.

- **`cache_control` → DeepSeek-specific format** — DeepSeek's automatic prefix
  detection works well enough (97% hit rate) without explicit markers.
  Low priority.
