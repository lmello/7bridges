# Troubleshooting

Common problems and how to fix them. For setup help, see [GETTING_STARTED.md](GETTING_STARTED.md).

---

## "command not found: uv"

`uv` is not installed or not in your PATH.

**Fix:** Follow the install instructions in [GETTING_STARTED.md](GETTING_STARTED.md#platform-specific-setup). After installing, you may need to restart your terminal or run `source ~/.bashrc` (or `source ~/.zshrc` on macOS).

---

## "No module named 'seven_bridges'"

The virtual environment is not activated, or the install step was skipped.

**Fix:**

```bash
cd /path/to/7bridges
source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## "Failed to connect" / "Connection refused" on port 4001

The bridge server is not running, or something else is using port 4001.

**Fix:**

```bash
# Check if the server is running
curl http://localhost:4001/v1/models

# If nothing responds, start it:
uvicorn seven_bridges.main:app --reload --port 4001

# If port 4001 is taken, use a different port:
uvicorn seven_bridges.main:app --reload --port 4002
# And update ANTHROPIC_BASE_URL accordingly
```

---

## "401 Unauthorized" or "403 Forbidden"

The `x-api-key` header doesn't match `BRIDGE_API_KEY`.

**Fix:** Make sure `ANTHROPIC_API_KEY` (in your Claude Code env) matches `BRIDGE_API_KEY` (in the bridge's env). They must be identical strings.

---

## "Model does not support image input" (with DeepSeek)

DeepSeek v4 does not support vision. Use a vision-capable backend like Kimi (`claude-opus-4-6`) or enable the experimental vision fallback. See [VISION_FALLBACK.md](VISION_FALLBACK.md).

---

## Claude Code still talks to Anthropic

Claude Code caches the base URL. After changing `ANTHROPIC_BASE_URL`, fully quit and restart Claude Code.

```bash
# Inside Claude Code, type:
/quit
# Then in your terminal:
export ANTHROPIC_BASE_URL="http://localhost:4001"
export ANTHROPIC_API_KEY="ollama"
claude
```

---

## Upstream returns "rate limit exceeded"

You've hit the provider's rate limit. Wait a minute and try again, or check your account's rate limits on the provider's dashboard.

---

## Tests fail during pre-commit

Make sure the virtual environment is activated and all dev dependencies are installed:

```bash
source .venv/bin/activate
uv pip install -e ".[dev]"
make check
```

---

## Still stuck?

If none of these fix your problem:

1. Enable debug logging: `make run-debug`
2. Try the verification tests in [GETTING_STARTED.md](GETTING_STARTED.md) (Test 1–3)
3. Check `logs/debug/` for the most recent session log
