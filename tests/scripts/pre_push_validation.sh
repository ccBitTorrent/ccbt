#!/bin/bash
set -e

echo "Running pre-push validation..."

# Run pre-commit hooks
echo "1. Running pre-commit hooks..."
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml

# Run quick test suite
echo "2. Running quick test suite..."
uv run pytest -c dev/pytest.ini tests/unit/ -v --maxfail=5

# Run type checking
echo "3. Running type checking..."
uv run ty check --config-file=dev/ty.toml --output-format=concise

echo "✅ Pre-push validation passed!"

