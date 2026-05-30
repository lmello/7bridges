# Anthropic Content Block Types

Reference of all content block types defined in the Anthropic Messages API,
sourced from the official SDK (`anthropic-sdk-python`).

Last updated: 2026-05-30 from SDK `types/content_block_param.py`.

## Request-side blocks (ContentBlockParam)

These appear in `messages[].content[]` and `system[]` arrays of incoming requests
from Claude Code. Our Pydantic union (`models/anthropic.py:ContentBlock`) must
cover every type Claude Code might send — a missing type causes a 400 validation
error.

| Block Type | In Our Model? | Description |
|---|---|---|
| `text` | ✅ `TextBlock` | Plain text content |
| `image` | ✅ `ImageBlock` | Base64-encoded image |
| `document` | ✅ `DocumentBlock` | Base64-encoded document (PDF, etc.) |
| `thinking` | ✅ `ThinkingBlock` | Reasoning/thinking content |
| `redacted_thinking` | ✅ `RedactedThinkingBlock` | Redacted thinking for safety |
| `tool_use` | ✅ `ToolUseBlock` | Assistant tool call |
| `tool_result` | ✅ `ToolResultBlock` | User-provided tool result |
| `server_tool_use` | ❌ | Server-initiated tool calls |
| `search_result` | ❌ | Search result content |
| `web_search_tool_result` | ❌ | Web search tool output |
| `web_fetch_tool_result` | ❌ | Web fetch tool output |
| `code_execution_tool_result` | ❌ | Code execution output (generic) |
| `bash_code_execution_tool_result` | ❌ | Bash execution output |
| `text_editor_code_execution_tool_result` | ❌ | Text editor execution output |
| `tool_search_tool_result` | ❌ | Tool search result |
| `container_upload` | ❌ | Container upload block |
| `mid_conversation_system` | ❌ | System message mid-conversation |

## Response-side blocks (ContentBlock)

These appear in upstream responses. Passthrough backends forward them natively.

| Block Type | In Our Model? | Description |
|---|---|---|
| `text` | ✅ | Text response |
| `thinking` | ✅ | Reasoning content |
| `redacted_thinking` | ✅ | Redacted reasoning |
| `tool_use` | ✅ | Tool call |
| `server_tool_use` | ❌ | Server tool call |
| `web_search_tool_result` | ❌ | Web search result |
| `web_fetch_tool_result` | ❌ | Web fetch result |
| `code_execution_tool_result` | ❌ | Code execution result |
| `bash_code_execution_tool_result` | ❌ | Bash execution result |
| `text_editor_code_execution_tool_result` | ❌ | Text editor execution result |
| `tool_search_tool_result` | ❌ | Tool search result |
| `container_upload` | ❌ | Container upload |

## Adding a new block type

1. Add the Pydantic model to `src/seven_bridges/models/anthropic.py`
2. Add it to the `ContentBlock` union
3. Handle it in `src/seven_bridges/translation/request.py`:
   - `_convert_user_content()` — map to text placeholder for OpenAI backends
   - `_tool_result_to_text()` — same for tool result content lists
4. Passthrough bridges (`is_passthrough = True`) forward it natively via `model_dump()`
5. Add tests in `tests/test_translation.py`
