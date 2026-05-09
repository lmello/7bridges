.PHONY: install dev lock start stop restart flush logs run-debug tail-logs test test-unit test-e2e test-smoke test-cov test-ci lint format check

install:
	uv venv --python 3.13
	.venv/bin/python -m pip install -e ".[dev]"

dev:
	.venv/bin/python -m pip install -e ".[dev]"

lock:
	uv pip compile pyproject.toml -o requirements.txt

start:
	pm2 start ecosystem.config.js

stop:
	pm2 delete 7-bridges-of-claude

restart:
	pm2 restart 7-bridges-of-claude

flush:
	rm -f logs/out.log logs/err.log

logs:
	pm2 logs 7-bridges-of-claude

run-debug:
	BRIDGE_DEBUG=1 .venv/bin/python -m uvicorn seven_bridges.main:app --host 0.0.0.0 --port 4001

tail-logs:
	@mkdir -p logs/debug
	@bash -c 'cd logs/debug && tail -f $$(ls -t *.jsonl | head -1) | jq --unbuffered .'

test:
	.venv/bin/pytest tests/ -v

test-unit:
	.venv/bin/pytest tests/test_translation.py tests/test_streaming.py -v

test-e2e:
	.venv/bin/pytest tests/test_e2e.py -v

test-smoke:
	.venv/bin/pytest tests/test_smoke.py -v

test-cov:
	.venv/bin/pytest tests/ --cov=src/seven_bridges --cov-report=term-missing --cov-report=html

test-ci:
	.venv/bin/pytest tests/ --cov=src/seven_bridges --cov-report=xml --cov-fail-under=85

lint:
	.venv/bin/ruff check src/ tests/
	.venv/bin/mypy src/

format:
	.venv/bin/ruff format src/ tests/

check: lint test
