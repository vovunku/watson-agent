# Makefile for audit agent

.PHONY: help dev test build run lint fmt clean install

# Load environment variables from .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Default target
help:
	@echo "Available targets:"
	@echo "  dev              - Run development server with hot reload"
	@echo "  dev-dry          - Run development server in DRY_RUN mode"
	@echo "  test             - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-full        - Run all tests (unit + integration)"
	@echo "  demo             - Run quick start demo"
	@echo "  demo-python      - Run Python client demo"
	@echo "  build            - Build Docker image"
	@echo "  run              - Run Docker container"
	@echo "  run-dry          - Run Docker container in DRY_RUN mode"
	@echo "  stop             - Stop and remove containers"
	@echo "  lint             - Run linting"
	@echo "  fmt              - Format code"
	@echo "  clean            - Clean up temporary files"
	@echo "  install          - Install dependencies"

# Development server
dev:
	@echo "Starting development server..."
	UVICORN_RELOAD=1 python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload

dev-dry:
	@echo "Starting development server in DRY_RUN mode..."
	UVICORN_RELOAD=1 DRY_RUN=true python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short

# Build Docker image
build:
	@echo "Building Docker image..."
	docker build -t audit-agent:latest .

# Run Docker container
run:
	@echo "Running Docker container..."
	docker run -d \
		--name audit-agent \
		-p 8081:8080 \
		-e OPENROUTER_API_KEY=$(OPENROUTER_API_KEY) \
		-e OPENROUTER_MODEL=$(OPENROUTER_MODEL) \
		-e DRY_RUN=false \
		audit-agent:latest

# Run Docker container in DRY_RUN mode
run-dry:
	@echo "Running Docker container in DRY_RUN mode..."
	docker run -d \
		--name audit-agent-dry \
		-p 8080:8080 \
		-e DRY_RUN=true \
		audit-agent:latest

# Stop and remove container
stop:
	@echo "Stopping and removing container..."
	docker stop audit-agent audit-agent-dry 2>/dev/null || true
	docker rm audit-agent audit-agent-dry 2>/dev/null || true

# Lint code (requires ruff)
lint:
	@echo "Running linter..."
	ruff check .

# Format code (requires black)
fmt:
	@echo "Formatting code..."
	black .

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements.txt
	pip install ruff black

# Database operations
db-init:
	@echo "Initializing database..."
	python -c "from db import init_db; init_db()"

db-migrate:
	@echo "Running database migrations..."
	alembic upgrade head

# Show logs
logs:
	@echo "Showing container logs..."
	docker logs -f audit-agent

# Shell into container
shell:
	@echo "Opening shell in container..."
	docker exec -it audit-agent /bin/bash

# Test API endpoints
test-api:
	@echo "Testing API endpoints..."
	@echo "Health check:"
	curl -s http://localhost:8080/healthz | jq .
	@echo "\nCreating test job:"
	curl -s -X POST http://localhost:8080/jobs \
		-H "Content-Type: application/json" \
		-d '{"source":{"type":"inline","inline_code":"contract Test { function test() public {} }"},"audit_profile":"erc20_basic_v1","idempotency_key":"test-123"}' | jq .

# Run integration tests
test-integration:
	@echo "Running integration tests..."
	python test_integration.py --url http://localhost:8081

# Run integration tests with custom URL
test-integration-custom:
	@echo "Running integration tests with custom URL..."
	python test_integration.py --url $(URL)

# Run quick start demo
demo:
	@echo "Running quick start demo..."
	./examples/quick_start.sh

# Run Python client demo
demo-python:
	@echo "Running Python client demo..."
	python examples/python_client.py

# Full test suite
test-full: test test-integration

# Production deployment
deploy:
	@echo "Deploying to production..."
	$(MAKE) build
	$(MAKE) stop
	$(MAKE) run
