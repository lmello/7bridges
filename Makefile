.PHONY: install dev start stop restart flush logs lint format test

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

test:
	.venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check src/
	.venv/bin/mypy src/

format:
	.venv/bin/ruff format src/
