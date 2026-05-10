"""Agent inference smoke tests.

Reads prompts from fixtures.json, sends them to the bridge, and evaluates
responses with a hybrid approach:

1. Rule-based checks (primary, deterministic)
2. LLM-as-judge (secondary, best-effort — upstream models return thinking-only
   output, so structured JSON extraction is unreliable)

Requires the bridge to be running and upstream API keys to be configured.

Run:
    BRIDGE_URL=http://localhost:4001 BRIDGE_API_KEY=ollama \
    uv run pytest tests/agent-inference/test_agent_inference.py -v

Or:
    make run-debug  # in another terminal
    make test-agent
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"
BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:4001")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "ollama")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-sonnet-4-6")
PASS_THRESHOLD = int(os.environ.get("PASS_THRESHOLD", "7"))


def _load_fixtures() -> list[dict[str, Any]]:
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _bridge_is_healthy() -> bool:
    try:
        r = httpx.get(f"{BRIDGE_URL}/health", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _bridge_is_healthy(),
    reason=f"Bridge not reachable at {BRIDGE_URL}",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call_bridge(
    messages: list[dict[str, str]],
    model_alias: str,
    max_tokens: int,
    stream: bool = False,
) -> dict[str, Any] | str:
    """Send a request to the bridge. Returns JSON dict (non-streaming) or
    reconstructed content dict (streaming)."""
    resp = httpx.post(
        f"{BRIDGE_URL}/v1/messages",
        headers={
            "x-api-key": BRIDGE_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "model": model_alias,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": stream,
        },
        timeout=120.0,
    )
    resp.raise_for_status()

    if not stream:
        return resp.json()

    # Parse SSE stream and reconstruct the response
    text_parts: list[str] = []
    thinking_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    current_tool: dict[str, Any] | None = None

    for line in resp.text.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]" or not data:
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")
        if etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text_parts.append(delta.get("text", ""))
            elif delta.get("type") == "thinking_delta":
                thinking_parts.append(delta.get("thinking", ""))
            elif delta.get("type") == "input_json_delta" and current_tool is not None:
                current_tool["arguments"] += delta.get("partial_json", "")
        elif etype == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                current_tool = {
                    "name": block.get("name", ""),
                    "id": block.get("id", ""),
                    "arguments": "",
                }
                tool_calls.append(current_tool)
        elif etype == "content_block_stop":
            current_tool = None

    return {
        "_source": "streaming_reconstructed",
        "text": "".join(text_parts),
        "thinking": "".join(thinking_parts),
        "tool_calls": tool_calls,
    }


def _extract_score_from_text(text: str) -> int:
    """Best-effort score extraction from free-form model output.

    Upstream vendors (Kimi, DeepSeek) return thinking-only output with no
    structured JSON. We apply a series of regex heuristics.
    """
    patterns = [
        r'"score"\s*:\s*(\d+)',
        r"score\s*[:=]?\s*(\d+)",
        r"(\d+)\s*out of\s*10",
        r"(\d+)/10",
        r"rate\s*(?:it|this)\s*(?:a|at)?\s*(\d+)",
        r"(?:give|assign)\s*(?:a|it)?\s*(\d+)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _judge(
    question: str,
    expected_behavior: str,
    actual_response: str,
) -> dict[str, Any]:
    """Ask a judge model to score the response.

    Returns {"score": int, "passed": bool, "notes": str}.
    Because upstream models return thinking-only output, score extraction
    is heuristic-based and best-effort.
    """
    judge_prompt = (
        "You are a strict test evaluator. Rate the following response.\n\n"
        f"Question: {question}\n\n"
        f"Expected behavior: {expected_behavior}\n\n"
        f"Actual response:\n{actual_response}\n\n"
        "Rate this response on a scale of 1-10 where:\n"
        "- 10 = Perfect match, fully satisfies expected behavior\n"
        "- 7-9 = Good match, minor issues\n"
        "- 4-6 = Partial match, significant issues\n"
        "- 1-3 = Poor match, fails expected behavior\n\n"
        f"A response PASSES if score >= {PASS_THRESHOLD}.\n\n"
        "End your response by stating the score clearly, e.g.:\n"
        f'"Score: 8/10. Passed: true."'
    )

    result = _call_bridge(
        messages=[{"role": "user", "content": judge_prompt}],
        model_alias=JUDGE_MODEL,
        max_tokens=500,
        stream=False,
    )

    # Extract all text/thinking content from the response
    combined = ""
    if isinstance(result, dict):
        for block in result.get("content", []):
            if block.get("type") == "text":
                combined += block.get("text", "")
            elif block.get("type") == "thinking":
                combined += block.get("thinking", "")
    else:
        combined = str(result)

    score = _extract_score_from_text(combined)
    return {
        "score": score,
        "passed": score >= PASS_THRESHOLD,
        "notes": combined[:300],
    }


# ---------------------------------------------------------------------------
# Rule-based checks
# ---------------------------------------------------------------------------


def _rule_based_check(test_id: str, response: str, checks: dict[str, Any]) -> list[str]:
    """Apply deterministic rule-based checks to a response."""
    failures: list[str] = []

    if not response.strip():
        failures.append("Response is empty")
        return failures

    must_contain = checks.get("must_contain", [])
    for phrase in must_contain:
        if phrase.lower() not in response.lower():
            failures.append(f"Missing required phrase: '{phrase}'")

    must_not_contain = checks.get("must_not_contain", [])
    for phrase in must_not_contain:
        if phrase.lower() in response.lower():
            failures.append(f"Forbidden phrase present: '{phrase}'")

    min_len = checks.get("min_length")
    if min_len is not None and len(response) < min_len:
        failures.append(f"Response too short ({len(response)} < {min_len})")

    max_len = checks.get("max_length")
    if max_len is not None and len(response) > max_len:
        failures.append(f"Response too long ({len(response)} > {max_len})")

    return failures


# ---------------------------------------------------------------------------
# Test parametrization
# ---------------------------------------------------------------------------


def _generate_test_cases() -> list[dict[str, Any]]:
    """Generate test-case dicts for parametrization."""
    cases: list[dict[str, Any]] = []
    for fixture in _load_fixtures():
        test_id = fixture["id"]
        for model in fixture.get("models", ["claude-sonnet-4-6"]):
            cases.append(
                {
                    "test_id": test_id,
                    "model_alias": model,
                    "fixture": fixture,
                }
            )
    return cases


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixtures() -> list[dict[str, Any]]:
    return _load_fixtures()


@pytest.mark.parametrize(
    "case",
    _generate_test_cases(),
    ids=lambda c: f"{c['test_id']}[{c['model_alias']}]",
)
def test_agent_inference(case: dict[str, Any]) -> None:
    """Run a single agent inference test against a specific model."""
    test_id = case["test_id"]
    model_alias = case["model_alias"]
    fixture = case["fixture"]
    automatable = fixture.get("automatable", True)
    messages = fixture["messages"]
    max_tokens = fixture.get("max_tokens", 500)
    stream = fixture.get("stream", True)
    checks = fixture.get("checks", {})

    # --- Phase 1: Call the bridge ---
    result = _call_bridge(
        messages=messages,
        model_alias=model_alias,
        max_tokens=max_tokens,
        stream=stream,
    )

    # --- Phase 2: Extract response text ---
    if isinstance(result, dict) and result.get("_source") == "streaming_reconstructed":
        text = result.get("text", "")
        thinking = result.get("thinking", "")
        tool_calls = result.get("tool_calls", [])
    elif isinstance(result, dict):
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        thinking = ""
        for block in result.get("content", []):
            if block.get("type") == "thinking":
                thinking += block.get("thinking", "")
        tool_calls = []
        for block in result.get("content", []):
            if block.get("type") == "tool_use":
                tool_calls.append({"name": block.get("name", ""), "id": block.get("id", "")})
    else:
        text = str(result)
        thinking = ""
        tool_calls = []

    # Some models emit all content as thinking with no text
    full_response = text or thinking

    # For non-automatable tool-use tests, just verify a tool_use block was emitted
    if not automatable:
        if len(tool_calls) > 0:
            expected_tool = fixture.get("expected_tool")
            if expected_tool:
                names = [tc.get("name", "") for tc in tool_calls]
                assert expected_tool in names, (
                    f"{test_id}[{model_alias}]: Expected tool '{expected_tool}', got {names}"
                )
            pytest.skip(
                f"{test_id}[{model_alias}]: Tool-use block verified; "
                f"full test requires tool-executing client"
            )
        else:
            # No tool_use emitted — judge the text answer instead
            pass

    # --- Phase 3: Rule-based checks (primary) ---
    rule_failures = _rule_based_check(test_id, full_response, checks)
    rule_passed = len(rule_failures) == 0

    # --- Phase 4: LLM judge (secondary, best-effort) ---
    question = messages[0]["content"]
    expected = fixture["expected_behavior"]
    verdict = _judge(question, expected, full_response)

    score = verdict.get("score", 0)
    judge_passed = verdict.get("passed", False)
    notes = verdict.get("notes", "")

    # Check for known issues on this model
    known_issues = fixture.get("known_issues", {})
    known_issue = known_issues.get(model_alias)

    # Print for visibility
    print(f"\n[{test_id} @ {model_alias}]")
    print(f"  response_length={len(full_response)}")
    print(f"  rule_checks={'PASS' if rule_passed else 'FAIL'} ({len(rule_failures)} failures)")
    print(f"  judge_score={score}/10 judge_passed={judge_passed}")
    if rule_failures:
        for f in rule_failures:
            print(f"    RULE: {f}")
    if known_issue and not rule_passed:
        print(f"    KNOWN ISSUE: {known_issue}")
    print(f"  notes: {notes[:200]}\n")

    # Final assertion — xfail for known issues instead of hard failure
    if known_issue and not rule_passed:
        pytest.xfail(f"{test_id}[{model_alias}]: Known issue — {known_issue}")

    assert rule_passed, (
        f"{test_id}[{model_alias}]: Rule-based checks failed: {'; '.join(rule_failures)}"
    )
