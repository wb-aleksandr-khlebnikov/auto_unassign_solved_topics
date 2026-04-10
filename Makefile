.PHONY: venv install lint format test run docker-build docker-up docker-down

venv:
	python -m venv .venv

install:
	pip install -e .[dev]

lint:
	ruff check app tests
	black --check app tests
	mypy app

format:
	ruff check --fix app tests
	black app tests

test:
	pytest -q

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
