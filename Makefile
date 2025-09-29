.PHONY: migrate dev test lint

migrate:
	. .venv/bin/activate && alembic upgrade head

dev:
	uvicorn netapi.app:app --reload --port 8000

test:
	PYTHONPATH=. pytest -q

lint:
	flake8 netapi tests
