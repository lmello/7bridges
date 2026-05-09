# Kimi Code API — Empirically Probed

**Base URL:** `https://api.kimi.com/coding/v1`

**Authentication:** Bearer token via `Authorization: Bearer <KIMI_CODE_API_KEY>`

**Critical: User-Agent gating.** The API checks `User-Agent` and rejects unknown agents:
- ✅ `User-Agent: claude-code/0.1.0` — works
- ❌ `User-Agent: kimi-cli/0.1.0` — rejected with `access_terminated_error`

## Available Endpoints

| Endpoint | Status |
|---|---|
| `GET /models` | ✅ Works |
| `POST /chat/completions` | ✅ Works |
| `POST /completions` | ❌ 404 |

## Models

| ID | Display Name | Context | Reasoning | Images | Video |
|---|---|---|---|---|---|
| `kimi-for-coding` | Kimi-k2.6 | 262,144 | ✅ | ✅ | ✅ |

## Non-Streaming Response Format

Standard OpenAI `chat.completion` with Kimi extensions:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "kimi-for-coding",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "final answer",
      "reasoning_content": "thinking process..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 17,
    "completion_tokens": 38,
    "total_tokens": 55,
    "cached_tokens": 11,
    "prompt_tokens_details": { "cached_tokens": 11 }
  }
}
```

## Streaming Response Format

Standard OpenAI SSE (`data: {...}`) with `delta.reasoning_content` preceding `delta.content`:

```
data:{"choices":[{"delta":{"reasoning_content":"Let me"},"finish_reason":null}]}
data:{"choices":[{"delta":{"reasoning_content":" think..."},"finish_reason":null}]}
data:{"choices":[{"delta":{"content":"OK"},"finish_reason":null}]}
data:{"choices":[{"delta":{},"finish_reason":"stop"}]}
data:[DONE]
```
