# Makefile for Konflux DevLake MCP Server
# Provides convenient commands for development, testing, and deployment

.PHONY: help install test test-unit test-security test-all lint format type-check clean run dev

# Default target
help: ## Show this help message
	@echo "Konflux DevLake MCP Server - Development Commands"
	@echo "=================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install: ## Install dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install pytest-cov pytest-timeout pytest-xdist

# Testing commands
test: test-unit ## Run unit tests (default)

test-unit: ## Run unit tests only (no external dependencies)
	python run_tests.py --unit --verbose

test-security: ## Run security-related tests
	python run_tests.py --security --verbose

test-all: ## Run all tests
	python run_tests.py --all --verbose

test-coverage: ## Run tests with coverage report
	python run_tests.py --unit --coverage

test-file: ## Run specific test file (usage: make test-file FILE=test_config.py)
	python run_tests.py --file $(FILE) --verbose

test-clean: ## Clean test artifacts and cache files
	python run_tests.py --clean

# Code quality
lint: ## Run code linting (flake8)
	python -m flake8 .

lint-black: ## Check code formatting with black
	python -m black --check --diff .

lint-mypy: ## Run type checking with mypy
	python -m mypy --ignore-missing-imports .

format: ## Format code with black
	python -m black .

format-check: ## Check code formatting without making changes
	python -m black --check .

type-check: ## Run type checking with mypy
	python -m mypy --ignore-missing-imports .

quality: lint lint-black lint-mypy ## Run all code quality checks

# Development commands
run: ## Run the MCP server in stdio mode
	python konflux-devlake-mcp.py --transport stdio

run-http: ## Run the MCP server in HTTP mode
	python konflux-devlake-mcp.py --transport http --host 0.0.0.0 --port 3000

dev: ## Run in development mode with debug logging
	python konflux-devlake-mcp.py --transport stdio --log-level DEBUG

# Docker commands
docker-build: ## Build Docker image
	docker build -t konflux-devlake-mcp .

docker-run: ## Run Docker container
	docker run -p 3000:3000 konflux-devlake-mcp

# Utility commands
clean: test-clean ## Clean all generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -f .coverage

check-deps: ## Check if all dependencies are installed
	python run_tests.py --check-deps

# CI/CD simulation
ci: clean install quality test-coverage ## Simulate CI pipeline locally

# Quick development workflow
quick-test: ## Quick test run (unit tests only, no verbose output)
	python -m pytest -m unit -q

watch-tests: ## Watch for file changes and run tests automatically (requires pytest-xdist)
	python -m pytest -m unit --looponfail

# Documentation
docs: ## Generate documentation (placeholder)
	@echo "Documentation generation not yet implemented"

# Release preparation
pre-commit: quality test-all ## Run pre-commit checks (quality + all tests)
	@echo "✅ Pre-commit checks completed successfully"

# Advanced testing
test-parallel: ## Run tests in parallel (requires pytest-xdist)
	python -m pytest -m unit -n auto

test-verbose: ## Run tests with maximum verbosity
	python -m pytest -m unit -vvv --tb=long

test-debug: ## Run tests with debugging enabled
	python -m pytest -m unit -vvv --tb=long --pdb

# Performance testing
test-performance: ## Run performance-related tests (placeholder)
	@echo "Performance tests not yet implemented"

# Integration testing (requires database)
test-integration: ## Run integration tests (requires database setup)
	@echo "Integration tests not yet implemented - requires database setup"

# Environment setup
setup-dev: install-dev ## Setup development environment
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify everything is working"

# Help for specific commands
help-test: ## Show detailed help for testing commands
	@echo "Testing Commands:"
	@echo "  test-unit      - Fast unit tests with mocked dependencies"
	@echo "  test-security  - Security-focused tests (SQL injection, etc.)"
	@echo "  test-all       - All tests including slower ones"
	@echo "  test-coverage  - Unit tests with HTML coverage report"
	@echo "  test-file      - Run specific test file: make test-file FILE=test_config.py"
	@echo "  quick-test     - Fast, quiet test run for development"
	@echo "  watch-tests    - Continuously run tests on file changes"

help-quality: ## Show detailed help for code quality commands
	@echo "Code Quality Commands:"
	@echo "  lint           - Check code style with flake8"
	@echo "  format         - Auto-format code with black"
	@echo "  format-check   - Check formatting without changes"
	@echo "  type-check     - Static type checking with mypy"
	@echo "  quality        - Run all quality checks"
