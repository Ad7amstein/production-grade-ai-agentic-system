SHELL := /bin/bash
ENV ?= development

install-dev:
	@echo "Installing dependencies..."
	@pip install --upgrade pip
	@uv pip install -e .[dev]

install-prod:
	@echo "Installing dependencies..."
	@pip install --no-deps --no-build-isolation --no-cache-dir --upgrade --force-reinstall .

docker-up:
	@echo "Starting docker containers..."
	@docker compose -f docker/docker-compose.yml up -d --build

docker-down:
	@echo "Stopping docker containers..."
	@docker compose -f docker/docker-compose.yml down

dev:
	@echo "Starting server in $(ENV) environment"
	@export APP_ENV=$(ENV) && uv run uvicorn main:app --reload --port 8000 --loop uvloop

clean:
	@echo "Cleaning up..."
	@rm -rf __pycache__ .pytest_cache dist build .venv *.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

help:
	@echo "Usage: make <target> [ENV=development|staging|production|test]"
	@echo "Targets:"
	@echo "  install-dev:  Install development dependencies"
	@echo "  install-prod: Install production dependencies"
	@echo "  docker-up:    Build and start docker containers"
	@echo "  docker-down:  Stop docker containers"
	@echo "  clean:        Clean up temporary files and caches"
	@echo "  help:         Show this help message"
