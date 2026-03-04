.PHONY: setup test lint type-check fmt clean

setup:
	uv sync

test:
	uv run pytest packages/ apps/

lint:
	uv run ruff check packages/ apps/

type-check:
	uv run mypy packages/schemas/src

fmt:
	uv run ruff format packages/ apps/
	uv run ruff check --fix packages/ apps/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
