# Cephly E-commerce AI Agent - Makefile
# ======================================

.PHONY: help install dev test build generate-api migrate lint

# Default target
help:
	@echo "Cephly Development Commands"
	@echo "=========================="
	@echo ""
	@echo "Setup:"
	@echo "  make install         Install all dependencies"
	@echo "  make dev             Start development environment"
	@echo ""
	@echo "API Client Generation:"
	@echo "  make generate-api    Generate TypeScript API client from OpenAPI"
	@echo ""
	@echo "Database:"
	@echo "  make migrate         Run database migrations"
	@echo "  make migrate-create  Create new migration"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests"
	@echo "  make test-backend    Run backend tests"
	@echo "  make test-frontend   Run frontend tests"
	@echo ""
	@echo "Linting:"
	@echo "  make lint            Run all linters"
	@echo "  make lint-backend    Run Python linters"
	@echo "  make lint-frontend   Run TypeScript linters"
	@echo ""
	@echo "Build:"
	@echo "  make build           Build production images"

# Installation
install:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Development
dev:
	docker-compose up -d

# Generate API Client
generate-api:
	@echo "Generating TypeScript API client..."
	chmod +x scripts/generate-api-client.sh
	./scripts/generate-api-client.sh

# Database Migrations
migrate:
	cd backend && alembic upgrade head

migrate-create:
	@read -p "Migration name: " name; \
	cd backend && alembic revision --autogenerate -m "$$name"

# Testing
test: test-backend test-frontend

test-backend:
	cd backend && pytest

test-frontend:
	cd frontend && npm test

# Linting
lint: lint-backend lint-frontend

lint-backend:
	cd backend && flake8 app --max-line-length=120 --extend-ignore=E203,W503
	cd backend && black app --check
	cd backend && isort app --check-only

lint-frontend:
	cd frontend && npm run lint

format-backend:
	cd backend && black app
	cd backend && isort app

# Build
build:
	docker-compose -f docker-compose.yml build

# Clean
clean:
	docker-compose down -v
	docker system prune -f

# Health Check
health:
	@curl -s http://localhost:8000/health | jq .
