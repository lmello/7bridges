#!/usr/bin/env python3
"""Validate that a commit message follows the Conventional Commits spec.

Hook type: commit-msg
Usage: python scripts/validate_commit_msg.py <commit-msg-file>
"""

import re
import sys

# Conventional Commits regex
# Matches: type(scope)!: description
# Types: https://www.conventionalcommits.org/en/v1.0.0/#summary
PATTERN = re.compile(
    r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(\([a-z0-9._-]+\))?"
    r"!?: .+$"
)

# Allowed exceptions that bypass the check
EXCEPTION_PREFIXES = (
    "Merge ",
    "Revert ",
    "Release ",
    "BREAKING CHANGE:",
)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 1

    commit_msg_file = sys.argv[1]
    with open(commit_msg_file, encoding="utf-8") as f:
        raw = f.read()

    # Only validate the subject line (first non-empty, non-comment line)
    first_line = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        first_line = stripped
        break

    if not first_line:
        # Empty commit message — git itself will reject this
        return 0

    if first_line.startswith(EXCEPTION_PREFIXES):
        return 0

    if PATTERN.match(first_line):
        return 0

    print(
        "\n"
        "ERROR: Commit message does not follow Conventional Commits.\n"
        "\n"
        "Expected format:\n"
        "  <type>[(scope)][!]: <description>\n"
        "\n"
        "Valid types:\n"
        "  build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test\n"
        "\n"
        "Examples:\n"
        "  feat: add streaming support for Kimi backend\n"
        "  fix(translation): handle empty reasoning_content chunks\n"
        "  docs(readme): update setup instructions\n"
        "\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
