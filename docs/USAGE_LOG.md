# Usage Logging

Every successful chat completion is automatically logged to `logs/usage.jsonl` with detailed token accounting and request metadata. This is useful for cost tracking, usage analysis, and debugging unexpected bills.

---

## Overview

| Property | Value |
|---|---|
| **Log file** | `logs/usage.jsonl` |
| **Format** | JSON Lines (one JSON object per line) |
| **Enabled by** | Always on — no configuration required |
| **Failures** | Silently ignored — logging never breaks a request |
| **Currently wired for** | Kimi backend (other backends coming) |

---

## Logged Fields

Each line contains the following fields:

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 string | When the request completed (UTC) |
| `session_id` | `string \| null` | Claude Code session ID from `x-claude-code-session-id` header |
| `client_app` | `string \| null` | Client identifier (`cli`, etc.) |
| `user_agent` | `string \| null` | Full User-Agent header |
| `api_key_prefix` | `string \| null` | First 8 characters of the API key used (for key rotation tracking) |
| `bridge` | `string` | Backend name: `kimi`, `deepseek`, `siliconflow`, `fireworks`, `ollama` |
| `model_alias` | `string` | The alias the client requested (e.g. `claude-opus-4-6`) |
| `backend_model` | `string` | The actual upstream model name (e.g. `kimi-for-coding`) |
| `response_id` | `string \| null` | Upstream response ID |
| `stream` | `boolean` | Whether the request used streaming |
| `max_tokens` | `integer \| null` | `max_tokens` from the request |
| `thinking_enabled` | `boolean \| null` | Whether reasoning/thinking was enabled |
| `thinking_budget` | `string \| null` | `output_config.effort` value (`low`, `medium`, `high`, etc.) |
| `tool_count` | `integer` | Number of tools provided in the request |
| `tool_names` | `string[]` | Names of the tools provided |
| `message_count` | `integer` | Number of messages in the conversation |
| `has_images` | `boolean` | Whether the request included image blocks |
| `has_video` | `boolean` | Whether the request included video blocks |
| `temperature` | `number \| null` | Sampling temperature |
| `top_p` | `number \| null` | Nucleus sampling parameter |
| `stop_reason` | `string \| null` | Why the model stopped (`end_turn`, `max_tokens`, `tool_use`) |
| `client_metadata` | `object \| null` | Arbitrary metadata object from the request |
| `usage` | `object` | Token counts (see below) |

### Usage Sub-Object

```json
{
  "prompt_tokens": 100,
  "completion_tokens": 50,
  "total_tokens": 150,
  "cached_tokens": 25,
  "prompt_cache_hit_tokens": null,
  "prompt_cache_miss_tokens": null
}
```

| Field | Description |
|---|---|
| `prompt_tokens` | Tokens in the prompt |
| `completion_tokens` | Tokens in the response |
| `total_tokens` | Sum of prompt + completion |
| `cached_tokens` | Kimi-style cached prompt tokens |
| `prompt_cache_hit_tokens` | DeepSeek-style cache hit tokens |
| `prompt_cache_miss_tokens` | DeepSeek-style cache miss tokens |

Note: only one caching style is typically populated per backend. The others are `null`.

---

## Example Queries

### Read the last 5 entries

```bash
cd logs && tail -n 5 usage.jsonl | jq .
```

### Total tokens today

```bash
cd logs && jq -s '
  map(select(.timestamp | startswith("'$(date -u +%Y-%m-%d)'")))
  | map(.usage.total_tokens)
  | add
' usage.jsonl
```

### Tokens by backend

```bash
cd logs && jq -s '
  group_by(.bridge)
  | map({
      bridge: .[0].bridge,
      requests: length,
      total_tokens: map(.usage.total_tokens) | add
    })
' usage.jsonl
```

### Find the most expensive session

```bash
cd logs && jq -s '
  group_by(.session_id)
  | map({
      session: .[0].session_id,
      requests: length,
      total_tokens: map(.usage.total_tokens) | add
    })
  | sort_by(.total_tokens)
  | reverse
  | .[:5]
' usage.jsonl
```

### Filter for streaming requests with thinking enabled

```bash
cd logs && jq 'select(.stream == true and .thinking_enabled == true)' usage.jsonl
```

---

## Log Rotation

There is no automatic rotation. The file grows indefinitely while the server runs. To manage size:

```bash
# Rotate manually (move and compress)
mv logs/usage.jsonl logs/usage-$(date +%Y%m%d).jsonl
gzip logs/usage-$(date +%Y%m%d).jsonl

# The next request will create a fresh usage.jsonl
```

For production deployments, consider a cron job or logrotate.

---

## Privacy Notes

- **No message content** is logged — only metadata and token counts.
- **No full API keys** are logged — only an 8-character prefix.
- **No PII** from the request body is captured beyond what the client sends in `metadata`.

---

## Integration Status

| Backend | Usage Logging | Notes |
|---|---|---|
| Kimi | Yes | Full support — streaming and non-streaming |
| DeepSeek | No | Planned |
| SiliconFlow | No | Planned |
| Fireworks AI | No | Planned |
| Ollama | No | Not applicable (local, free) |

To add usage logging to a backend, call `_log_usage()` from `seven_bridges.usage_log` in the bridge's `chat()` and `chat_stream()` methods, passing `self.usage_context` (populated automatically by `main.py`).
