# CCBT BitTorrent Client - Development Makefile

.PHONY: help install lint format type-check test test-cov test-cov-html test-cov-xml test-cov-term codecov security docs clean pre-commit setup-dev

# Default target
help:
	@echo "CCBT BitTorrent Client - Development Commands"
	@echo "=============================================="
	@echo ""
	@echo "UV Commands (Recommended):"
	@echo "  install      Install dependencies with UV"
	@echo "  lint         Run linting checks (ruff)"
	@echo "  format       Format code (ruff)"
	@echo "  type-check   Run type checking (ty)"
	@echo "  test         Run tests"
	@echo "  test-cov     Run tests with coverage (all formats)"
	@echo "  test-cov-html Run tests with HTML coverage report"
	@echo "  test-cov-xml  Run tests with XML coverage report"
	@echo "  test-cov-term Run tests with terminal coverage report"
	@echo "  codecov      Upload coverage to codecov.io"
	@echo "  security     Run security scan (bandit)"
	@echo "  docs         Build documentation (mkdocs)"
	@echo "  pre-commit   Run pre-commit on all files"
	@echo "  clean        Clean up temporary files"
	@echo ""

# Install dependencies
install:
	uv sync --dev

# Set up development environment
setup-dev:
	@echo "Installing UV if not present..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Installing UV..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	uv sync --dev
	pre-commit install
	pre-commit install --hook-type commit-msg

# Lint code
lint:
	uv run ruff check ccbt/ --fix --exit-non-zero-on-fix

# Format code
format:
	uv run ruff format ccbt/

# Type check
type-check:
	uv run ty check --config-file=ty.toml --output-format=concise

# Run tests
test:
	uv run pytest tests/ -v --tb=short --maxfail=5 --timeout=60

# Run tests with coverage (all formats)
test-cov:
	uv run pytest tests/ --cov=ccbt --cov-report=html --cov-report=xml --cov-report=term-missing

# Run tests with HTML coverage report
test-cov-html:
	uv run pytest tests/ --cov=ccbt --cov-report=html
	@echo "HTML coverage report generated in htmlcov/index.html"

# Run tests with XML coverage report
test-cov-xml:
	uv run pytest tests/ --cov=ccbt --cov-report=xml
	@echo "XML coverage report generated in coverage.xml"

# Run tests with terminal coverage report
test-cov-term:
	uv run pytest tests/ --cov=ccbt --cov-report=term-missing

# Upload coverage to codecov.io
codecov: test-cov-xml
	@echo "Uploading coverage to codecov.io..."
	uv run codecov --file coverage.xml --flags unittests
	@echo "Coverage uploaded successfully!"

# Security scan
security:
	uv run bandit -r ccbt/ -f json -o bandit-report.json --severity-level medium --exclude tests/

# Build documentation
docs:
	uv run mkdocs build --strict

# Run pre-commit on all files
pre-commit:
	uv run pre-commit run --all-files

# Clean up temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".ruff_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name "htmlcov" -delete
	find . -type f -name "bandit-report.json" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf .uv/
