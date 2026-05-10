# Session Handoff Report

**Date:** 2026-05-12
**Project:** 7-bridges-of-claude (`~/Dev/vibe/7-bridges-of-claude`)
**Branch:** `main` → `origin/main` (`e864fab`)

---

## What This Project Is

An **Anthropic Messages API proxy** that lets Claude Code talk to non-Anthropic LLMs (DeepSeek, Kimi) through explicit, tested translations.

**Model mapping:**
| Alias | Backend | Actual Model | Context | Max Output |
|-------|---------|-------------|---------|------------|
| `claude-haiku-4-5` | DeepSeek | `deepseek-v4-flash` | 1M | 384K |
| `claude-sonnet-4-6` | DeepSeek | `deepseek-v4-pro` | 1M | 384K |
| `claude-opus-4-6` | Kimi | `kimi-for-coding` (K2.6) | 262K | 32K |
| `claude-haiku-4-5-20251001` | DeepSeek | `deepseek-v4-flash` | 1M | 384K |

**Port:** 4001 (PM2-managed, PID 51635)

---

## Everything We Did This Session

### 1. count_tokens Endpoint
- Added `POST /v1/messages/count_tokens` with local token estimation (~4 chars/token)
- Claude Code uses this to check token budget; was returning 404, causing retries

### 2. Streaming Usage Fix
- Added `stream_options={"include_usage": true}` to upstream OpenAI requests
- `translate_openai_stream` now captures usage from final delta chunks (not just usage-only chunks)
- Statusline now shows non-zero in/out tokens

### 3. Context Window Metadata
- `/v1/models` returns `context_window` and `max_output_tokens` per model
- Claude Code reads these for `[1m]`/`[262k]` display

### 4. Debug Log Truncation
- 50 KB cap per log entry
- Large request bodies replaced with summary: `{"_truncated": true, "_original_bytes": N, "message_count": M}`

### 5. Tail-Logs Auto-Switch
- `make tail-logs` now follows newest debug log file across PM2 restarts via bash loop

### 6. Agent Inference Test Framework (14 tests)
- Parametrized across 3 models × 5 fixtures
- Hybrid evaluation: rule-based checks (primary) + LLM judge (secondary)
- Judge extracts scores from thinking-only output via 6 regex patterns
- `known_issues` per model → `pytest.xfail` (Kimi jailbreak non-determinism)

### 7. Live Streaming Smoke Tests
- `tests/test_smoke_streaming.py` verifies streaming end-to-end for all 3 models

### 8. Auto-approve Dynamic Discovery
- `scripts/auto-approve.ts` (committed to `~/.claude` repo, `08e18c1`)
- Queries `/v1/models` to discover haiku model dynamically
- Works across litellm/7-bridges/Anthropic

### 9. Diagnostic Logging
- `logs/diagnostics.jsonl` captures 400 error details (validation, upstream, unknown model)
- Helped identify root cause of phantom alias 400s

---

## Critical Code Changes (by file)

| File | What Changed |
|------|-------------|
| `src/seven_bridges/config.py` | Added `claude-haiku-4-5-20251001` alias |
| `src/seven_bridges/main.py` | Added `count_tokens`, diagnostic logging, context window in `/v1/models` |
| `src/seven_bridges/debug.py` | 50 KB log truncation, large body summaries |
| `src/seven_bridges/backends/deepseek.py` | `stream_options={"include_usage": true}` |
| `src/seven_bridges/backends/kimi.py` | `stream_options={"include_usage": true}` |
| `src/seven_bridges/translation/stream.py` | Usage extraction from final delta chunks |
| `src/seven_bridges/models/openai.py` | Added `StreamOptions` model |
| `tests/agent-inference/test_agent_inference.py` | 14 parametrized tests, hybrid evaluation |
| `tests/test_smoke_streaming.py` | Live streaming smoke tests |
| `Makefile` | `tail-logs` auto-switch loop, `test-agent`, `test-smoke-streaming` targets |

---

## Current State of the Bridge

| Metric | Value |
|--------|-------|
| Process | PID 51635, online |
| Port | 4001 |
| Health | `{"status":"ok"}` |
| Debug logging | Enabled (`BRIDGE_DEBUG=1`) |
| Last restart | Before some config changes (see below) |

**All tests pass:**
- 61 unit tests: ✅
- 14 agent inference tests: ✅
- 3 live streaming smoke tests: ✅
- Lint (ruff + mypy): ✅

---

## ⚠️ Active Issues & Notes

1. **Bridge restart pending:** PID 51635 was last restarted *before* some fixes. The following are in the codebase but may not be active until next restart:
   - `claude-haiku-4-5-20251001` alias
   - Diagnostic logging (`_log_diagnostic`)
   - `count_tokens` endpoint (may work — FastAPI reloads routes, but model resolution might not)
   - **DO NOT restart while active agents are running.**

2. **Phantom alias 400s (intermittent):** Other Claude Code instances (PIDs 25505, 93350) may use `claude-haiku-4-5-20251001` for background tasks. The new alias in config will fix this after restart.

3. **Kimi jailbreak non-determinism:** `password-fake-constraints` on `claude-opus-4-6` sometimes leaks "blueberry". Documented as known issue with xfail.

4. **Tool-use tests non-automatable:** `stream-file-analysis` requires real tool-executing client. Test verifies `tool_use` block emission then skips.

5. **Env var hygiene:** Current shell has only `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY`. No `ANTHROPIC_DEFAULT_*_MODEL` vars.

6. **Multiple Claude Code instances:** Three instances running (PIDs 64156 — current, 93350, 25505).

---

## How to Start Claude Code with This Bridge

```bash
export ANTHROPIC_BASE_URL="http://localhost:4001"
export ANTHROPIC_API_KEY="ollama"
claude
```

Then inside Claude Code:
```
/model claude-sonnet-4-6   # DeepSeek V4 Pro (best for heavy tasks)
/model claude-opus-4-6     # Kimi K2.6 (best for coding/reasoning)
/model claude-haiku-4-5    # DeepSeek V4 Flash (fast/cheap)
```

---

## Where to Pick Up

- The bridge is **stable for development tasks**
- All fixes are committed and pushed to `origin/main` (`e864fab`)
- Next action: restart bridge when no agents are active, to pick up config changes
- Monitor `logs/diagnostics.jsonl` for any new 400s after restart
