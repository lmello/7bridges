.PHONY: install dev lock start stop restart flush logs run-debug tail-logs test test-unit test-e2e test-smoke test-cov test-ci test-full lint format check

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
	pm2 delete 7bridges

restart:
	pm2 restart 7bridges

flush:
	rm -f logs/out.log logs/err.log

logs:
	pm2 logs 7bridges

run-debug:
	BRIDGE_DEBUG=1 .venv/bin/python -m uvicorn seven_bridges.main:app --host 0.0.0.0 --port 4001

tail-logs:
	@mkdir -p logs/debug
	@echo "Following newest debug log (auto-switches on new files)..."
	@bash -c 'cd logs/debug && \
		while true; do \
			newest=$$(ls -t *.jsonl 2>/dev/null | head -1); \
			[ -z "$$newest" ] && sleep 1 && continue; \
			echo "==> Tailing: $$newest" >&2; \
			tail -n0 -f "$$newest" & pid=$$!; \
			while [ "$$(ls -t *.jsonl 2>/dev/null | head -1)" = "$$newest" ]; do \
				sleep 1; \
			done; \
			kill $$pid 2>/dev/null; \
			wait $$pid 2>/dev/null; \
			echo "==> Newer log detected, switching..." >&2; \
		done \
	' | jq --unbuffered .

test:
	.venv/bin/pytest tests/ -v --ignore=tests/agent-inference

test-agent:
	.venv/bin/pytest tests/agent-inference/ -v

test-unit:
	.venv/bin/pytest tests/test_translation.py tests/test_streaming.py -v

test-e2e:
	.venv/bin/pytest tests/test_e2e.py -v

test-smoke:
	.venv/bin/pytest tests/test_smoke.py -v

test-cov:
	.venv/bin/pytest tests/ --cov=src/seven_bridges --cov-report=term-missing --cov-report=html

test-ci:
	.venv/bin/pytest tests/ --cov=src/seven_bridges --cov-report=xml --cov-fail-under=85 --ignore=tests/agent-inference --ignore=tests/test_smoke_streaming.py

lint:
	.venv/bin/ruff check src/ tests/
	.venv/bin/mypy src/

format:
	.venv/bin/ruff format src/ tests/

test-full:
	.venv/bin/pytest tests/ -v

check: lint test

version:
	.venv/bin/semantic-release version

changelog:
	.venv/bin/semantic-release changelog
