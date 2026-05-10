# Claude Code Bridge Test Suite

Run these three prompts against the bridge to verify reasoning, tool use, and
multi-step logic translation. Run once with a **DeepSeek** model alias and once
with a **Kimi** model alias.

---

## Test 1 — Pure Reasoning with Fake Constraints

**Purpose:** Validates `thinking` blocks and text output. No tool use.

**Prompt:**
> I have three rules for my password: it must be exactly 8 characters, contain
> at least one prime number digit, and no two consecutive characters can be the
> same letter. But wait — the second rule is fake, I just made it up. The real
> constraints are: exactly 8 chars, no repeated consecutive characters, and at
> least one symbol. Generate a valid password and tell me which rule you ignored
> and why.

---

## Test 2 — Reasoning + Tool Use with Conflicting Constraints

**Prompt:**
> Check the file `src/seven_bridges/translation/stream.py` and tell me: if I
> wanted to add a new SSE event type called `content_block_pause`, what lines
> would I need to touch? But there's a catch — I also want to maintain backward
> compatibility so old clients that don't understand `pause` events still work.
> Walk me through your reasoning, then propose the minimal code change.

**Instructions for Claude Code:** Run from the repo root so the `Read` tool can
find the file. Do not modify any file — this is read-only analysis.

---

## Test 3 — Multi-Hop Reasoning with Arithmetic Traps

**Prompt:**
> A bat and a ball cost $11 total. The bat costs $10 more than the ball. I also
> have a constraint that the ball must cost an integer number of dollars, and
> another constraint that the total must be divisible by 3. But one of these
> constraints makes the problem impossible. Identify which constraint is the
> problem, drop it, solve for bat and ball prices, and verify the remaining
> constraints are satisfied. Show your reasoning step by step.

---

## How to Run

### DeepSeek
```bash
export ANTHROPIC_BASE_URL="http://localhost:4001"
export ANTHROPIC_API_KEY="ollama"
claude
# Then in Claude Code: /model claude-opus-4-6
```

### Kimi (Opus stand-in)
```bash
export ANTHROPIC_BASE_URL="http://localhost:4001"
export ANTHROPIC_API_KEY="ollama"
claude
# Then in Claude Code: /model claude-sonnet-4-6
```

### Check debug logs after each test
```bash
cd ~/Dev/vibe/7-bridges-of-claude && make tail-logs
```

Look for:
- `content_block_start` with `type: thinking`
- `content_block_delta` chunks with reasoning text
- `content_block_stop`
- `message_delta` with `stop_reason` (if applicable)
