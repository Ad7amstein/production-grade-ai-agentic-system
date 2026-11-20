SHELL := /bin/bash
APP_ENV ?= development

install-dev:
	@echo "Installing dependencies..."
	@pip install --upgrade pip
	@uv pip install -e .[dev]

install-prod:
	@echo "Installing dependencies..."
	@pip install --no-deps --no-build-isolation --no-cache-dir --upgrade --force-reinstall .

docker-build:
	@echo "Building docker image ($(APP_ENV))..."
	@APP_ENV=$(APP_ENV) docker compose build app

docker-up:
	@echo "Starting docker containers ($(APP_ENV))..."
	@APP_ENV=$(APP_ENV) docker compose up -d --build

docker-down:
	@echo "Stopping docker containers..."
	@APP_ENV=$(APP_ENV) docker compose down

run-dev:
	@bash scripts/run_app.sh --mode dev

run-prod:
	@bash scripts/run_app.sh --mode prod

migrate:
	@echo "Applying database migrations ($(APP_ENV))..."
	@APP_ENV=$(APP_ENV) uv run alembic upgrade head

migration:
	@test -n "$(MSG)" || (echo 'Usage: make migration MSG="describe the change"' && exit 1)
	@echo "Creating migration: $(MSG) ($(APP_ENV))..."
	@APP_ENV=$(APP_ENV) uv run alembic revision --autogenerate -m "$(MSG)"

refresh-model-profiles:
	@echo "Refreshing $(PROFILE_PROVIDER) model profiles from models.dev..."
	@langchain-profiles refresh --provider $(PROFILE_PROVIDER) --data-dir src/services/llm/model_profiles/$(PROFILE_PROVIDER)

clean:
	@echo "Cleaning up..."
	@rm -rf __pycache__ .pytest_cache dist build .venv *.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

help:
	@echo "Usage: make <target> [APP_ENV=development|production]"
	@echo "Targets:"
	@echo "  install-dev:  Install development dependencies"
	@echo "  install-prod: Install production dependencies"
	@echo "  docker-build: Build the app image (APP_ENV=, default development)"
	@echo "  docker-up:    Build and start docker containers (APP_ENV=, default development)"
	@echo "  docker-down:  Stop docker containers"
	@echo "  run-dev:      Install dev deps and run via scripts/run_app.sh"
	@echo "  run-prod:     Install prod deps and run via scripts/run_app.sh"
	@echo "  migrate:      Apply all pending database migrations (APP_ENV=, default development)"
	@echo "  migration:    Autogenerate a new migration from model changes (MSG=\"...\" required)"
	@echo "  refresh-model-profiles: Refresh model profiles from models.dev"
	@echo "  clean:        Clean up temporary files and caches"
	@echo "  help:         Show this help message"
