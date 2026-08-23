.PHONY: dev up down build migrate test lint format demo demo-change clean
dev:
	docker compose up --build
up:
	docker compose up -d
down:
	docker compose down
build:
	docker compose build
migrate:
	docker compose run --rm api alembic upgrade head
test:
	pytest
lint:
	ruff check . && mypy watchtower
format:
	ruff format . && ruff check --fix .
demo:
	docker compose --profile demo up --build
demo-change:
	curl -fsS -X POST http://localhost:8080/change
clean:
	docker compose down --remove-orphans

