.PHONY: install run test test-unit test-integration clean

install:
	python -m venv venv
	venv/bin/pip install -r requirements.txt

run:
	venv/bin/uvicorn backend.main:app --reload --port 8000

test:
	venv/bin/pytest tests/

test-unit:
	venv/bin/pytest tests/unit/

test-integration:
	venv/bin/pytest tests/integration/

clean:
	rm -rf venv __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
