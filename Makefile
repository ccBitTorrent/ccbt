# CCBT BitTorrent Client - Development Makefile

.PHONY: help install lint format type-check test test-cov clean pre-commit setup-dev

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
	@echo "  test-cov     Run tests with coverage"
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
	uv run ruff check .

# Format code
format:
	uv run ruff format .

# Type check
type-check:
	uv run ty .

# Run tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=ccbt --cov-report=html --cov-report=term

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
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf .uv/
