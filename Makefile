.PHONY: help up down build logs ps migrate reset-db api-shell bot-shell

help:   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: copy .env.example → .env
	@[ -f .env ] && echo ".env already exists" || (cp .env.example .env && echo "Copied .env.example to .env — EDIT IT before running 'make up'")

build:  ## Build all Docker images
	docker compose build --no-cache

up:     ## Start all services (detached)
	docker compose up -d
	@echo ""
	@echo "  API docs  → http://localhost:8000/docs"
	@echo "  MinIO     → http://localhost:9001  (minioadmin / see .env)"
	@echo ""

dev:    ## Start all services, stream logs
	docker compose up

down:   ## Stop all services
	docker compose down

logs:   ## Tail logs for all services
	docker compose logs -f

api-logs:  ## Tail API logs only
	docker compose logs -f api

bot-logs:  ## Tail bot logs only
	docker compose logs -f bot

ps:     ## Show service status
	docker compose ps

migrate: ## Run Alembic migrations (runs automatically on 'up')
	docker compose run --rm migrate

reset-db: ## ⚠️  Drop and recreate the database (DEV ONLY)
	docker compose down -v postgres
	docker compose up -d postgres
	sleep 5
	docker compose run --rm migrate

api-shell: ## Open Python shell inside the API container
	docker compose exec api python

bot-shell: ## Open shell inside the bot container
	docker compose exec bot bash

clean:  ## Remove all containers, images, volumes
	docker compose down -v --rmi local
