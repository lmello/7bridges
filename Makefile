.PHONY: dev install test lint format start

install:
	uv venv --python 3.13
	.venv/bin/python -m pip install -e ".[dev]"

dev:
	.venv/bin/python -m pip install -e ".[dev]"

start:
	.venv/bin/uvicorn seven_bridges.main:app --host 0.0.0.0 --port 4000 --reload

test:
	.venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check src/
	.venv/bin/mypy src/

format:
	.venv/bin/ruff format src/
