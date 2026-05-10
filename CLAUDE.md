# Agent Guide for 7 Bridges of Claude

This document governs how AI agents (Claude Code, Kimi, etc.) should work with this repository. Instructions here override defaults and README summaries.

## Project Identity

This is an **Anthropic Messages API proxy** — a translation layer, not a generic LLM gateway. Every backend bridge explicitly maps Anthropic-native concepts (thinking blocks, tool_use, cache tokens) to upstream formats and back. There is no "pass-through" mode.

## Development Cadence

### 1. Small, Tested Changes

- **One concern per commit.** A commit should touch either translation logic, a backend, tests, or docs — not all four at once unless the change is trivial.
- **Never commit without running tests.** The pre-commit gate requires 80% coverage and all 58 tests passing.
- **Prefer fixing over adding.** If a feature can be achieved by tightening existing translation rather than adding new endpoints, do that.

### 2. Test-First for Translation Logic

Any change to `src/seven_bridges/translation/` must have a corresponding test in `tests/test_translation.py` or `tests/test_streaming.py` **before** the implementation change is committed. E2E tests (`tests/test_e2e.py`) are for integration validation, not unit-level edge cases.

### 3. Backend Changes Require Capability Audit

When modifying a backend (`src/seven_bridges/backends/*.py`), always check `VendorCapabilities`:

- `supports_vision` — does this upstream accept image blocks?
- `supports_reasoning` — does it return reasoning content?
- `supports_tools` — does it handle function calling?

If you add a capability, update the backend class, add an E2E test, and update the model listing in `src/seven_bridges/config.py`.

### 4. Debug Middleware is Sacred

The debug logger (`src/seven_bridges/debug.py`) is the primary diagnostic tool for live Claude Code sessions. Changes here must:

- Preserve the JSONL per-session format
- Maintain backward compatibility in log structure (new fields are fine; removing fields is not)
- Pass `tests/test_debug.py`

## Testing Integrity & Consistency

### Running Tests

```bash
# Full suite (what pre-commit runs)
make check        # lint + unit tests

# With coverage report
make test-cov

# Granular suites
make test-unit     # translation + streaming (61 tests)
make test-e2e      # mocked upstream HTTP round-trips
make test-smoke    # API basics
make test-agent    # agent inference tests against live upstreams (14 tests)
make test-smoke-streaming  # live streaming smoke tests against all 3 models
```

### Coverage Gate

- **Minimum: 80%** (enforced by pre-commit)
- **Target: 90%+** for `translation/` and `backends/`
- Coverage regressions are blockers. If you refactor and drop coverage, add tests.

### Lint & Type Check

```bash
make lint         # ruff + mypy
make format       # ruff format
```

Rules are strict (`mypy --strict`, `ruff` with `UP` and `B` rules). Type ignores are acceptable for Starlette internals or third-party oddities, but must include a `# noqa` or comment explaining why.

### Pre-Commit Hook Order

1. **gitleaks** — no secrets in commits
2. **ruff check** — lint must pass
3. **ruff format** — auto-format
4. **mypy** — strict type checking
5. **pytest** — all 61 unit tests + 14 agent inference tests, 80% coverage gate

If any step fails, the commit is rejected. Fix and retry.

## File Ownership

| Path | What lives here | Change policy |
|---|---|---|
| `src/seven_bridges/translation/` | Request/response/stream mapping | Unit-test every branch |
| `src/seven_bridges/backends/` | HTTP clients + capability flags | E2E test + capability audit |
| `src/seven_bridges/models/` | Pydantic schemas | Only add fields; never remove without deprecation |
| `src/seven_bridges/debug.py` | Request/response logging + error handling + log cleanup | Keep structure stable; rebuild StreamingResponse properly, never mutate internals |
| `tests/` | All tests | Mirror the source structure |
| `docs/` | Architecture diagrams, API specs | Update when behavior changes |

## Common Pitfalls

- **Thinking signatures:** Anthropic cryptographically signs thinking blocks. Upstream vendors don't. The bridge uses `_SIGNATURE_PLACEHOLDER` (empty string) consistently across `models/`, `translation/stream.py`, and `translation/response.py`. Do not attempt to generate fake signatures — Claude Code accepts empty ones.
- **SSE format variance:** Kimi sends `data:{...}` (no space). DeepSeek sends `data: {...}`. The parser handles both; never tighten the parser to assume one format.
- **Image flattening:** When a `tool_result` contains images, they must be flattened into separate `image_url` content blocks in the OpenAI request. Do not nest them under the tool result.
- **Tool result translation:** In the Anthropic API, `tool_result` blocks live inside user-role messages. OpenAI requires them as separate `role: "tool"` messages with `tool_call_id`, placed immediately after the assistant's `tool_calls`. `_convert_messages()` in `request.py` extracts `ToolResultBlock`s and emits them as `tool` role dicts. Any remaining text/image content stays in a separate `user` message. Never fold tool results into user message text.
- **StreamingResponse internals:** `BaseHTTPMiddleware` wraps `StreamingResponse` in a private `_StreamingResponse` class. `isinstance()` is unreliable; use `_is_streaming_response()` in `debug.py`. When rebuilding a stream after capture, construct a new `StreamingResponse` with the replay generator — do not mutate `body_iterator` directly.

## Commit Messages

Use conventional commits:

```
fix(translation): handle empty reasoning_content chunks
feat(kimi): add vision support for image blocks
test(e2e): cover 429 rate-limit error mapping
docs(architecture): update mermaid diagrams
```

## When to Ask the User

- Adding a new backend (new vendor, not just a new model)
- Changing the Anthropic API surface (new endpoints, breaking response format changes)
- Dropping support for an existing backend
- Modifying the auth scheme or API key handling
- Any change that would require Claude Code users to update their config
