# Makefile for Konflux DevLake MCP Server
# Provides convenient commands for development, testing, and deployment

.PHONY: help install test test-unit test-all clean run dev

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



test-all: ## Run ALL tests (unit + security + integration + e2e)
	@echo "🚀 Running comprehensive test suite (unit + security + integration)..."
	@echo "📦 Starting MySQL database..."
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 35
	@echo "🧪 Running all tests (unit + security + integration)..."
	@python run_tests.py --all --verbose; \
	CORE_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	docker compose down -v || docker-compose down -v; \
	echo "✅ Database cleaned up"; \
	if [ $$CORE_RESULT -ne 0 ]; then \
		echo "❌ Core tests failed"; \
		exit $$CORE_RESULT; \
	fi; \
	echo "🤖 Running LLM E2E tests..."; \
	$(MAKE) --no-print-directory test-e2e; \
	E2E_RESULT=$$?; \
	if [ $$E2E_RESULT -ne 0 ]; then \
		echo "❌ E2E tests failed"; \
		exit $$E2E_RESULT; \
	fi; \
	echo ""; \
	echo "✅ All tests passed (core + e2e)"

test-file: ## Run specific test file (usage: make test-file FILE=test_config.py)
	python run_tests.py --file $(FILE) --verbose

test-clean: ## Clean test artifacts and cache files
	python run_tests.py --clean


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
	rm -rf .pytest_cache

check-deps: ## Check if all dependencies are installed
	python run_tests.py --check-deps

# CI/CD simulation
ci-quick: clean install test-unit ## Quick CI check (unit (includes security), no database)

ci: clean install test-all ## Full CI pipeline (all tests with database)

# Quick development workflow
quick-test: ## Quick test run (unit tests only, no verbose output)
	python -m pytest -m unit -q

watch-tests: ## Watch for file changes and run tests automatically (requires pytest-xdist)
	python -m pytest -m unit --looponfail

# Documentation
docs: ## Generate documentation (placeholder)
	@echo "Documentation generation not yet implemented"

# Release preparation
pre-commit: test-all ## Run pre-commit checks (all tests)
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
test-integration: ## Run integration tests (handles setup and teardown automatically)
	@echo "🚀 Starting integration tests with database setup..."
	@echo "📦 Starting MySQL database..."
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Running integration tests..."
	@python run_tests.py --integration --verbose; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	docker compose down -v || docker-compose down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

test-e2e: ## Run LLM E2E tests (requires API keys; models via E2E_TEST_MODELS)
	@echo "🤖 Running LLM E2E tests..."
	@echo "   Models: $${E2E_TEST_MODELS:-gemini/gemini-2.5-pro,gpt-4o,claude-3-5-sonnet-20240620}"
	@if [ -z "$$OPENAI_API_KEY" ] && [ -z "$$ANTHROPIC_API_KEY" ] && [ -z "$$GEMINI_API_KEY" ]; then \
		echo "❌ No LLM API keys set. Set at least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY."; \
		exit 1; \
	fi
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 25
	@echo "🧪 Initializing database (via container mysql client)..."
	@docker compose exec -T mysql mysql -uroot -ptest_password -e "DROP DATABASE IF EXISTS lake; CREATE DATABASE lake;"
	@docker compose exec -T mysql mysql -uroot -ptest_password lake < testdata/mysql/01-schema.sql
	@docker compose exec -T mysql mysql -uroot -ptest_password lake < testdata/mysql/02-test-data.sql
	@echo "🧪 Running tests (stdio by default)..."
	@LITELLM_LOGGING=0 LITELLM_DISABLE_LOGGING=1 LITELLM_VERBOSE=0 LITELLM_LOGGING_QUEUE=0 pytest tests/e2e -vv --maxfail=1 --tb=short; \
	TEST_RESULT=$$?; \
	echo "🧹 Cleaning up database..."; \
	docker compose down -v || docker-compose down -v; \
	echo "✅ Database cleaned up"; \
	exit $$TEST_RESULT

 

test-integration-setup: ## Start database services for integration tests (manual setup)
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose up -d mysql; \
	else \
		docker compose up -d mysql; \
	fi
	@echo "Waiting for database to be ready..."
	@sleep 15
	@echo "Database should be ready."

test-integration-teardown: ## Stop database services (manual teardown)
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose down -v; \
	else \
		docker compose down -v; \
	fi

# Environment setup
setup-dev: install-dev ## Setup development environment
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify everything is working"

# Help for specific commands
help-test: ## Show detailed help for testing commands
	@echo "Testing Commands:"
	@echo ""
	@echo "  Quick Tests (No Database):"
	@echo "    test-unit        - Unit tests only (91 tests, ~3 seconds)"
	@echo "    (security tests are included in unit)"
	@echo "    quick-test       - Fast, quiet unit test run"
	@echo ""
	@echo "  Comprehensive Tests (Auto Database Setup):"
	@echo "    test-integration - Integration tests (62 tests, ~60 seconds, auto setup/teardown)"
	@echo "    test-all         - ALL 188 tests (unit + security + integration, auto setup/teardown)"
	@echo ""
	@echo "  E2E Tests (Requires LLM API Keys):"
	@echo "    test-e2e         - E2E tests with LLM integration"
	@echo "                       Default: gpt-4o, claude-3-5-sonnet-20240620"
	@echo "                       Override: E2E_TEST_MODELS='gemini/gemini-2.5-pro'"
	@echo "                       Note: Gemini requires 'gemini/' prefix"
	@echo "                       Requires: API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY)"
	@echo ""
	@echo "  Utilities:"
	@echo "    test-file        - Run specific test: make test-file FILE=test_config.py"
	@echo "    watch-tests      - Continuously run tests on file changes"
	@echo "    test-clean       - Clean test artifacts and cache"
	@echo ""
	@echo "  CI/CD:"
	@echo "    ci-quick         - Fast CI check (unit incl. security, no database)"
	@echo "    ci               - Full CI pipeline (all tests with database)"
