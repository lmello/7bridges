# Usage Logging

Every successful chat completion is automatically logged to `logs/usage.jsonl` with detailed token accounting and request metadata. Failed requests are logged to `logs/errors.jsonl`. A web dashboard is available for real-time monitoring.

---

## Web Dashboard

The easiest way to explore usage data is the built-in dashboard:

```bash
# Start the dashboard (runs on port 4002 alongside the bridge)
make dashboard

# Or start both bridge and dashboard together
make start-all
```

Open **http://localhost:4002** in your browser.

The dashboard provides:
- **Stat cards** — total requests, tokens in/out, estimated cost, cache hit rate, error rate
- **Time-series charts** — requests/hour, tokens/hour, and cost/hour over the last 24 hours with backend filtering
- **Backend breakdown table** — per-backend request counts, token usage, cost, latency, and error rates
- **Model breakdown table** — per-model usage and cost breakdown
- **Session table** — top sessions by request count and cost
- **Recent errors table** — last 50 errors with status codes, error types, and latency
- **Recent requests table** — last 50 requests with token counts, cost, and stream flags
- **Auto-refresh** — refreshes every 10 seconds; green/red dot indicates fetch status
- **Backend filter** — pill buttons to toggle specific backends on/off across all views

### Launch options

| Command | Description |
|---|---|
| `make dashboard` | Start dashboard via PM2 on port 4002 |
| `make dashboard-stop` | Stop the dashboard PM2 process |
| `make dashboard-restart` | Restart dashboard |
| `make dashboard-logs` | Tail dashboard PM2 logs |
| `make dashboard-run` | Run dashboard directly via uvicorn (no PM2, for development) |
| `make start-all` | Start both bridge (port 4001) and dashboard (port 4002) |
| `make stop` | Stop both bridge and dashboard |

The dashboard runs as a separate PM2 process named `7bridges-dashboard`. It reads JSONL files directly — no database required. Memory stays under 256 MB as configured in PM2.

---

## Overview

| Property | Value |
|---|---|
| **Usage log** | `logs/usage.jsonl` |
| **Error log** | `logs/errors.jsonl` |
| **Format** | JSON Lines (one JSON object per line) |
| **Enabled by** | Always on — no configuration required |
| **Failures** | Silently ignored — logging never breaks a request |
| **Dashboard** | `http://localhost:4002` |

---

## Usage Log Fields (`usage.jsonl`)

Each line contains the following fields:

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 string | When the request completed (UTC) |
| `session_id` | `string \| null` | Claude Code session ID from `x-claude-code-session-id` header |
| `client_app` | `string \| null` | Client identifier (`cli`, etc.) |
| `user_agent` | `string \| null` | Full User-Agent header |
| `api_key_prefix` | `string \| null` | First 8 characters of the API key used |
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
| `estimated_cost_usd` | `number \| null` | Estimated cost in USD using default pricing |
| `latency_ms` | `number \| null` | Total request latency in milliseconds |
| `cache_headers_sent` | `boolean \| null` | Whether cache-related headers were included in the upstream request |
| `cache_hit_rate` | `number \| null` | Cache hit rate as percentage (0-100), or null if no cache data |
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

### Enriched Fields (new)

| Field | Description |
|---|---|
| `estimated_cost_usd` | Computed using default pricing: $0.40/M input, $4.00/M output, $0.15/M cached read. Rounded to 6 decimal places. |
| `latency_ms` | Wall-clock duration from backend request start to response completion. Measured by the base class timer. |
| `cache_headers_sent` | `true` if cache-related headers were sent to the upstream backend. Reserved for future per-backend cache configuration. |
| `cache_hit_rate` | Computed as `prompt_cache_hit_tokens / (hit + miss) * 100` when both cache fields are present. `null` otherwise. Rounded to 1 decimal place. |

> **Note on cost:** The default pricing is a fixed estimate and does not reflect actual vendor billing. Per-model pricing overrides will be added in a future release.

---

## Error Log Fields (`errors.jsonl`)

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 string | When the error occurred (UTC) |
| `session_id` | `string \| null` | Claude Code session ID |
| `bridge` | `string` | Backend name |
| `model_alias` | `string` | The alias the client requested |
| `backend_model` | `string` | The actual upstream model name |
| `status_code` | `integer` | HTTP status code from the upstream backend |
| `error_type` | `string` | Anthropic-style error type (`rate_limit_error`, `authentication_error`, `api_error`, etc.) |
| `error_message` | `string` | Error message truncated to 500 characters |
| `stream` | `boolean` | Whether the request used streaming |
| `latency_ms` | `number \| null` | Total request latency up to the error point |
| `tool_count` | `integer` | Number of tools in the request |
| `has_images` | `boolean` | Whether images were present |
| `has_video` | `boolean` | Whether video was present |
| `client_app` | `string \| null` | Client identifier |

---

## Pricing

Default cost estimation uses these rates:

| Token type | Price per 1M tokens |
|---|---|
| Input (prompt) | $0.40 |
| Output (completion) | $4.00 |
| Cached read | $0.15 |
| Cached write | Same as input ($0.40) |

Formula: `(input * 0.40 + output * 4.00 + cache_read * 0.15) / 1_000_000`

Per-backend and per-model pricing overrides are planned for a future release. Open an issue to request support for your provider's actual rates.

---

## Example Queries

### Read the last 5 usage entries

```bash
tail -n 5 logs/usage.jsonl | jq .
```

### Total cost today

```bash
jq -s '
  map(select(.timestamp | startswith("'$(date -u +%Y-%m-%d)'")))
  | map(.estimated_cost_usd // 0) | add
' logs/usage.jsonl
```

### Cost by backend

```bash
jq -s '
  group_by(.bridge)
  | map({
      bridge: .[0].bridge,
      requests: length,
      cost: (map(.estimated_cost_usd // 0) | add)
    })
' logs/usage.jsonl
```

### Cache hit rate by backend

```bash
jq -s '
  group_by(.bridge)
  | map({
      bridge: .[0].bridge,
      requests: length,
      avg_cache_hit: (map(.cache_hit_rate) | add / length)
    })
' logs/usage.jsonl
```

### Average latency by backend

```bash
jq -s '
  group_by(.bridge)
  | map({
      bridge: .[0].bridge,
      avg_latency_ms: ((map(.latency_ms // 0) | add) / length)
    })
' logs/usage.jsonl
```

### Recent errors

```bash
tail -n 20 logs/errors.jsonl | jq '{ts: .timestamp, bridge, status: .status_code, type: .error_type, msg: .error_message}'
```

---

## Log Rotation

There is no automatic rotation. The files grow indefinitely while the server runs. To manage size:

```bash
# Rotate manually
mv logs/usage.jsonl logs/usage-$(date +%Y%m%d).jsonl
gzip logs/usage-$(date +%Y%m%d).jsonl

# The next request creates a fresh file
```

If you run the bridge via PM2, install `pm2-logrotate`:

```bash
make setup-logs
```

This installs `pm2-logrotate` and configures it to rotate logs at 10 MB, keeping the last 10 compressed backups.

---

## Privacy Notes

- **No message content** is logged — only metadata and token counts.
- **No full API keys** are logged — only an 8-character prefix.
- **No PII** from the request body is captured beyond what the client sends in `metadata`.

---

## Integration Status

| Backend | Usage Logging | Error Logging | Latency | Cost |
|---|---|---|---|---|
| Kimi | Yes | Yes | Yes | Yes |
| DeepSeek | Yes | Yes | Yes | Yes |
| SiliconFlow | Yes | Yes | Yes | Yes |
| Fireworks AI | Yes | Yes | Yes | Yes |
| Ollama | Yes | Yes | Yes | Yes |

All backends use the shared logging infrastructure in the `Bridge` base class. To add usage logging to a new backend, call `self.start_timer()` before the upstream request and `self._log_usage_from_context()` / `self._log_error_from_context()` after.
