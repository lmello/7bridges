# Contributing to 7 Bridges of Claude

## Workflow

1. [Fork the repo](https://github.com/sdkks/7bridges/fork)
2. Clone your fork:

   ```bash
   git clone https://github.com/<your-username>/7bridges.git
   cd 7-bridges-of-claude
   ```

3. Create a branch for your changes:

   ```bash
   git checkout -b my-feature
   ```

## Setup

```bash
# Install Python 3.13 and dev dependencies
make install

# Activate the venv
source .venv/bin/activate
```

## Pre-commit hooks

Install [pre-commit](https://pre-commit.com/) and the project hooks:

```bash
pre-commit install          # install git hook scripts
pre-commit install -t commit-msg  # install commit-msg hook for conventional commits
```

The hooks run in this order on every commit:

1. **gitleaks** — scans for secrets
2. **ruff check** — lint
3. **ruff format** — auto-format
4. **mypy** — strict type checking
5. **pytest** — all 61 unit tests, 80% coverage gate

If any step fails, the commit is rejected. Fix and retry.

## Before opening a PR

1. Run the full check suite locally: `make check`
2. Write or update tests — coverage must stay at 80%+
3. Use [conventional commit](https://www.conventionalcommits.org/) messages (e.g. `fix(translation): handle empty reasoning_content chunks`)
4. Push your branch to your fork and [open a PR](https://github.com/sdkks/7bridges/compare) against `sdkks/7bridges`

## Project structure

| Directory                        | Purpose                                       |
| -------------------------------- | --------------------------------------------- |
| `src/seven_bridges/translation/` | Anthropic ↔ upstream request/response mapping |
| `src/seven_bridges/backends/`    | HTTP clients + vendor capability flags        |
| `src/seven_bridges/models/`      | Pydantic schemas                              |
| `src/seven_bridges/debug.py`     | Request/response debug logging                |
| `tests/`                         | Unit, E2E, and smoke tests                    |

See [CLAUDE.md](CLAUDE.md) for detailed development policies and common pitfalls.
