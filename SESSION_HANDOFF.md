# Session Handoff Report

**Date:** 2026-05-13
**Project:** 7-bridges-of-claude (`~/Dev/vibe/7-bridges-of-claude`)
**Branch:** `main` → `origin/main` (`git@github.com:7bridges/7bridges.git`)

---

## What This Project Is

An **Anthropic Messages API proxy** that lets Claude Code (and other Anthropic clients) talk to non-Anthropic LLMs through explicit, tested translations. Every field that crosses the boundary is deliberately mapped.

**Model mapping:**
| Alias | Backend | Actual Model | Context | Max Output |
|-------|---------|-------------|---------|------------|
| `claude-haiku-4-5` | DeepSeek | `deepseek-v4-flash` | 1M | 384K |
| `claude-sonnet-4-6` | DeepSeek | `deepseek-v4-pro` | 1M | 384K |
| `claude-opus-4-6` | Kimi | `kimi-for-coding` (K2.6) | 262K | 32K |

**Port:** 4001 (PM2-managed)

---

## Everything We Did This Session

### 1. Debug Middleware Hardening
- Replaced broken `time.strftime` with `datetime.now(UTC).isoformat()`
- Added `handler_latency_ms`, `stream_duration_ms`, `duration_ms`
- Replaced `setattr(body_iterator)` hack with proper `StreamingResponse` rebuild
- Added try/except around stream consumption (returns 500 on failure)
- Added log cleanup: keeps only 100 most recent debug logs
- Fixed bytes concatenation inefficiency (`chunks.append()` + `b"".join()`)

### 2. Tool Result Translation Fix
- `ToolResultBlock` was being folded into user messages as text
- Fixed to emit proper OpenAI `tool` role messages with `tool_call_id`
- Added error flag: prefixes `[Error]` when `ToolResultBlock.is_error` is true
- Added 3 unit tests for this

### 3. Thinking Signature Constant
- Added `_SIGNATURE_PLACEHOLDER = ""` in `models/anthropic.py` with docstring
- Used everywhere instead of hardcoded `""`
- Anthropic cryptographically signs thinking blocks; upstream vendors (Kimi, DeepSeek) do not provide signatures

### 4. Streaming State Machine Hardening
- Added 3 edge-case tests: interleaved thinking+tool_calls, multiple tool calls, finish in same chunk
- All pass

### 5. Agent Inference Test Framework (`tests/agent-inference/`)

Created a complete integration test suite that reads JSON fixtures, calls the bridge via HTTP, and evaluates responses.

**Evaluation strategy:**
1. **Rule-based checks** (primary, deterministic): `must_contain`, `must_not_contain`, `min_length`, `max_length`
2. **LLM-as-judge** (secondary, best-effort): Regex heuristics extract scores from thinking-only output

**Test fixtures (5 total, 14 parametrized cases):**

| Fixture | Models Tested | What It Tests |
|---------|:-------------:|---------------|
| `password-fake-constraints` | All 3 | Jailbreak resistance (fake override instruction) |
| `bat-ball-arithmetic-traps` | All 3 | Multi-hop reasoning (correct answer: $0.05) |
| `code-fizzbuzz-one-liner` | All 3 | Code generation with constraints |
| `logic-wason-selection` | All 3 | Logic puzzle (correct answer: A and 7) |
| `stream-file-analysis` | Sonnet, Opus | Tool use emission (non-automatable — skips after verifying tool_use block) |

**Known issue tracking:**
- `known_issues` field per fixture → `pytest.xfail` for documented upstream quirks
- Kimi K2.6 is non-deterministically vulnerable to simple jailbreak (sometimes leaks "blueberry")

**Run:**
```bash
make test-agent          # 14 integration tests
make test                # 61 unit tests (excludes agent tests)
make check               # lint + unit tests
```

### 6. Live Streaming Smoke Test
- `tests/test_smoke_streaming.py` — hits real upstream APIs with streaming for all 3 models
- Verifies SSE format, content_block_delta presence, and response content
- All 3 pass

### 7. Context Window Metadata
- Added `context_window` and `max_output_tokens` to `ModelRoute` dataclass
- Updated `/v1/models` endpoint to expose these fields
- Claude Code reads context windows from the model list response
- PM2 restarted to pick up changes

### 8. Documentation
- Updated `tests/agent-inference/README.md` with run instructions and known issues
- Updated `Makefile` with `test-agent` target

### 9. Git Operations
- Commit: `9935af6` — *feat: agent inference test framework + live streaming smoke tests*
- Pushed to `git@github.com:7bridges/7bridges.git`
- All files clean on `main`

---

## Critical Code Changes (by file)

| File | What Changed |
|------|-------------|
| `src/seven_bridges/config.py` | Added `context_window`, `max_output_tokens` to `ModelRoute`; set per-model values |
| `src/seven_bridges/main.py` | `/v1/models` now returns `context_window` + `max_output_tokens` |
| `src/seven_bridges/debug.py` | Hardened middleware: proper StreamingResponse rebuild, error handling, log cleanup |
| `src/seven_bridges/translation/request.py` | ToolResultBlock → proper OpenAI `tool` role messages |
| `src/seven_bridges/translation/stream.py` | Existing streaming translation (no changes this session) |
| `src/seven_bridges/models/anthropic.py` | Added `_SIGNATURE_PLACEHOLDER` constant |
| `tests/agent-inference/fixtures.json` | 5 test fixtures |
| `tests/agent-inference/test_agent_inference.py` | Parametrized runner with hybrid evaluation |
| `tests/agent-inference/README.md` | Documentation |
| `tests/test_smoke_streaming.py` | Live streaming smoke test |
| `tests/test_streaming.py` | +3 edge-case tests |
| `tests/test_translation.py` | +3 tool result tests |
| `Makefile` | Added `test-agent` target |
| `ecosystem.config.js` | `BRIDGE_DEBUG: '1'` set |

---

## Current State of the Bridge

| Metric | Value |
|--------|-------|
| Process | PID 79730, online, 5m uptime (restarted with latest changes) |
| Port | 4001 |
| Health | `{"status":"ok"}` |
| Debug logging | Enabled (`BRIDGE_DEBUG=1`) |
| PM2 restarts | 20 total (historical — current instance stable) |

**All tests pass:**
- 61 unit tests: ✅
- 14 agent inference tests: ✅
- 3 live streaming smoke tests: ✅
- Lint (ruff + mypy): ✅

---

## Known Issues & Quirks

1. **Kimi K2.6 jailbreak vulnerability**: Non-deterministically leaks "blueberry" on simple override jailbreak. Marked as `xfail` in tests.

2. **Kimi thinking-only output**: Sometimes returns all content as `thinking_delta` with no `text_delta`. The reconstruction logic handles this (`text or thinking` fallback), but clients should be aware.

3. **Tool use tests non-automatable**: The `stream-file-analysis` fixture requires a tool-executing client (Claude Code). The automated test only verifies a `tool_use` block was emitted, then skips.

4. **LLM judge is best-effort**: Upstream models return thinking-only output, so structured JSON score extraction uses regex heuristics. Judge scores are informational; rule-based checks determine pass/fail.

5. **Model name confusion**: There's also a `litellm-bridge` process running (port unknown, PID 8783). Make sure `ANTHROPIC_BASE_URL` points to **4001**.

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

- The bridge is **stable and ready for development tasks**
- Heavy task was just started with DeepSeek Pro (sonnet); user will ask to "check logs" for irregularities
- Debug log: `logs/debug/0ca68c51.jsonl` (baseline: 406 KB at session start)
- `logs/out.log`: 403 lines, `logs/err.log`: 1,642 lines (baseline positions captured)
