# Makefile for Konflux DevLake MCP Server
# Provides convenient commands for development, testing, and deployment

.PHONY: help install install-dev test test-unit test-all test-file test-clean run run-http dev docker-build docker-run clean check-deps ci-quick ci quick-test watch-tests docs pre-commit test-parallel test-verbose test-debug test-performance test-integration test-e2e test-integration-setup test-integration-teardown setup-dev help-test

# Default target
help:
	@echo "Konflux DevLake MCP Server - Development Commands"
	@echo "=================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest-cov pytest-timeout pytest-xdist

# Testing commands
test-unit:
	python run_tests.py --unit --verbose

test-integration:
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

test-e2e:
	@echo "🤖 Running LLM E2E tests..."
	@{ \
	  if [ -n "$$E2E_TEST_MODELS" ]; then \
	    IFS=,; out=""; \
	    for m in $$E2E_TEST_MODELS; do \
	      case "$$m" in \
	        gemini/*) [ -n "$$GEMINI_API_KEY" ] && out="$${out:+$${out},}$$m" ;; \
	        gpt-4o*) [ -n "$$OPENAI_API_KEY" ] && out="$${out:+$${out},}$$m" ;; \
	        claude-*) [ -n "$$ANTHROPIC_API_KEY" ] && out="$${out:+$${out},}$$m" ;; \
	        *) out="$${out:+$${out},}$$m" ;; \
	      esac; \
	    done; \
	    echo "   Models: $${out:-none}"; \
	  else \
	    out=""; \
	    [ -n "$$GEMINI_API_KEY" ] && out="$${out:+$${out},}gemini/gemini-2.5-pro"; \
	    [ -n "$$OPENAI_API_KEY" ] && out="$${out:+$${out},}gpt-4o"; \
	    [ -n "$$ANTHROPIC_API_KEY" ] && out="$${out:+$${out},}claude-3-5-sonnet-20240620"; \
	    echo "   Models: $${out:-none}"; \
	  fi; \
	}
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

test-all:
	@echo "🚀 Running comprehensive test suite..."
	@echo "📦 Starting MySQL database..."
	@docker compose up -d mysql || docker-compose up -d mysql
	@echo "✅ Database container started"
	@echo "⏳ Waiting for database to be ready..."
	@sleep 35
	@echo "🧪 Running all tests..."
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
	echo "✅ All tests passed"

test-file:
	python run_tests.py --file $(FILE) --verbose

test-clean:
	python run_tests.py --clean

# Docker commands
docker-build: ## Build Docker image
	docker build -t konflux-devlake-mcp .

docker-run: ## Run Docker container
	docker run -p 3000:3000 konflux-devlake-mcp

# Utility commands
clean: test-clean
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache

check-deps:
	python run_tests.py --check-deps

# Environment setup
setup-dev: install-dev
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify everything is working"

# Help for specific commands
help-test:
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
