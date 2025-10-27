# Migration Guide: Modern Python Tooling

This guide helps you migrate from the old development tooling to the new Astral UV-based tools.

## What Changed

### Old Tools → New Tools
- **Black** → **Ruff** (formatting)
- **isort** → **Ruff** (import sorting)
- **flake8** → **Ruff** (linting)
- **mypy** → **Ty** (type checking)
- **pip + virtualenv** → **UV** (package management)

### Removed Files
The following legacy files have been removed and replaced by `pyproject.toml` + UV:
- `setup.py` - Legacy setuptools script
- `setup.cfg` - Legacy configuration file
- `setup_dev.py` - Custom setup script
- `requirements.txt` - Dependency list
- `mypy.ini` - Type checker configuration

### Benefits of the New Tools
- **10-100x faster** than the old tools
- **Single tool** for linting and formatting (Ruff)
- **Better error messages** and suggestions
- **Modern Python features** support
- **Unified configuration** in `pyproject.toml`
- **UV**: Ultra-fast package management (10-100x faster than pip)
- **Automatic virtual environment** management
- **Lock file** for reproducible builds

## Migration Steps

### 1. Install UV (One-time)
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Set Up Development Environment
```bash
# Install dependencies and create virtual environment
uv sync --dev

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg
```

### 3. Run Development Commands
```bash
# Format and lint code
make format
make lint

# Type check
make type-check

# Run tests
make test

# Run all checks
make pre-commit
```

## Simplified Workflow

### New Developer Onboarding
1. **Install UV**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Clone repository**: `git clone <repo> && cd <repo>`
3. **Install dependencies**: `uv sync --dev`
4. **Set up hooks**: `pre-commit install`
5. **Start developing**: `make test`, `make lint`, etc.

### Daily Development
```bash
# Install new dependencies
uv add requests

# Add development dependencies
uv add --group dev pytest-mock

# Run commands
uv run pytest
uv run ruff check .
uv run ty .

# Or use Make shortcuts
make test
make lint
make format
```

### Building and Publishing
```bash
# Build package
uv build

# Publish to PyPI
uv publish
```

## Configuration Files

### Current Configuration Files
- `pyproject.toml` - Main project configuration (dependencies, tools, build settings)
- `uv.toml` - UV-specific configuration
- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `uv.lock` - UV lock file for reproducible builds
- `Makefile` - Simplified development commands

### Configuration Consolidation
All tool configurations are now centralized in `pyproject.toml`:
- **Dependencies**: `[project]` and `[project.optional-dependencies]`
- **Ruff**: `[tool.ruff]` (linting and formatting)
- **Ty**: `[tool.ty]` (type checking)
- **Pytest**: `[tool.pytest.ini_options]` (testing)
- **Coverage**: `[tool.coverage.*]` (test coverage)
- **Bandit**: `[tool.bandit]` (security)
- **Commitizen**: `[tool.commitizen]` (commit messages)

## Troubleshooting

### Common Issues

1. **UV not found**: Install UV with `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Dependencies not found**: Run `uv sync --dev` to install all dependencies
3. **Pre-commit hooks failing**: Run `uv run pre-commit run --all-files` to see detailed errors
4. **Type checking errors**: Check `pyproject.toml` [tool.ty] configuration
5. **UV lock file issues**: Run `uv lock` to regenerate the lock file

### Getting Help

- **UV**: https://docs.astral.sh/uv/
- **Ruff**: https://docs.astral.sh/ruff/
- **Ty**: https://github.com/astral-sh/ty
- **Pre-commit**: https://pre-commit.com/
- **Project Issues**: Create an issue in the project repository

## UV Commands Reference

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync --dev

# Run commands in UV environment
uv run ruff check .
uv run pytest
uv run ty .

# Build package
uv build

# Publish package
uv publish

# Add new dependency
uv add requests

# Add development dependency
uv add --group dev pytest-mock

# Remove dependency
uv remove requests

# Update dependencies
uv lock --upgrade

# Show dependency tree
uv tree
```
