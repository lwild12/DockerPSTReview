.PHONY: up down build logs migrate makemigration test lint fmt shell-backend

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

makemigration:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

test:
	docker compose exec backend pytest

lint:
	docker compose exec backend ruff check app

fmt:
	docker compose exec backend ruff format app

shell-backend:
	docker compose exec backend bash
