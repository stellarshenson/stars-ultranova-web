.PHONY: install run test test-unit test-integration clean dev-install

install:
	uv sync

dev-install:
	uv sync --all-extras
	uv run playwright install chromium

run:
	uv run uvicorn backend.main:app --reload --port 8000

test:
	uv run pytest tests/

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest tests/integration/

clean:
	rm -rf .venv __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
