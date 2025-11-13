# Contributing to ccBitTorrent

Thank you for your interest in contributing to ccBitTorrent! This document outlines the development process, code standards, and contribution workflow.

## Project Overview

ccBitTorrent is a high-performance BitTorrent client implementation in Python. This is a **reference Python implementation** licensed under the **GPL**. The project aims to provide a complete, well-tested, and performant BitTorrent client.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- [UV](https://github.com/astral-sh/uv) package manager (recommended)
- Git

### Initial Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
```

2. Install dependencies using UV:
```bash
uv sync --dev
```

3. Install pre-commit hooks:
```bash
uv run pre-commit install --config dev/pre-commit-config.yaml
```

## Code Quality Standards

### Linting

We use [Ruff](https://github.com/astral-sh/ruff) for fast linting and formatting. Configuration is in [dev/ruff.toml](https://github.com/yourusername/ccbittorrent/blob/main/dev/ruff.toml).

Run linting:
```bash
uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
```

Format code:
```bash
uv run ruff --config dev/ruff.toml format ccbt/
```

### Type Checking

We use [Ty](https://github.com/astral-sh/ty) for fast type checking. Configuration is in [dev/ty.toml](https://github.com/yourusername/ccbittorrent/blob/main/dev/ty.toml).

Run type checking:
```bash
uv run ty check --config-file=dev/ty.toml --output-format=concise
```

### Testing

We use [pytest](https://pytest.org/) for testing. Configuration is in [dev/pytest.ini](https://github.com/yourusername/ccbittorrent/blob/main/dev/pytest.ini).

Run all tests:
```bash
uv run pytest -c dev/pytest.ini tests/ -v
```

Run with coverage:
```bash
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html --cov-report=xml
```

### Pre-commit Hooks

All quality checks run automatically via pre-commit hooks configured in [dev/pre-commit-config.yaml](https://github.com/yourusername/ccbittorrent/blob/main/dev/pre-commit-config.yaml). This includes:

- Ruff linting and formatting
- Ty type checking
- Bandit security scanning
- Pytest with coverage
- Benchmark smoke tests

Run manually:
```bash
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
```

## Development Configuration

All development configuration files are located in [dev/](dev/):

- [dev/pre-commit-config.yaml](https://github.com/yourusername/ccbittorrent/blob/main/dev/pre-commit-config.yaml) - Pre-commit hook configuration
- [dev/ruff.toml](https://github.com/yourusername/ccbittorrent/blob/main/dev/ruff.toml) - Ruff linting and formatting
- [dev/ty.toml](https://github.com/yourusername/ccbittorrent/blob/main/dev/ty.toml) - Type checking configuration
- [dev/pytest.ini](https://github.com/yourusername/ccbittorrent/blob/main/dev/pytest.ini) - Test configuration
- [dev/mkdocs.yml](https://github.com/yourusername/ccbittorrent/blob/main/dev/mkdocs.yml) - Documentation configuration

## Branch Strategy

### Main Branch

- The `main` branch is used for releases
- Only accepts merges from the `dev` branch
- Builds releases automatically on push to main

### Dev Branch

- The `dev` branch is the primary development branch
- **Only branch that merges to main**
- Runs all checks identically to main, including:
  - All linting and type checking
  - Full test suite with coverage
  - All benchmark checks from [dev/pre-commit-config.yaml:39-68](https://github.com/yourusername/ccbittorrent/blob/main/dev/pre-commit-config.yaml#L39-L68)
  - Documentation builds

### Feature Branches

Create feature branches directly from:
- **Sub-issues**: Branch directly from sub-issues if working on a specific part
- **Main issues**: Branch from main issues if addressing the full scope
- **GitHub Templates**: Use the GitHub issue template to create issues, then create a branch via the GitHub UI

## Issue Workflow

### Discussions

Development areas and features are discussed in GitHub Discussions. From these discussions come:

1. **Main Issues**: High-level feature or improvement requests
2. **Sub Issues**: Specific tasks or components related to a main issue

### Creating Issues

1. Use the GitHub issue template provided
2. Link to related discussions if applicable
3. Create issues for main features or sub-tasks as needed

### Branch Creation

- Create branches directly on sub-issues or main issues using GitHub UI
- Branch names should be descriptive and reference the issue number
- Example: `feature/dht-improvements-123` or `fix/peer-connection-bug-456`

## Contribution Process

### Making Changes

1. **Fork or create branch**: Create a branch from the appropriate issue
2. **Make changes**: Follow code quality standards
3. **Test locally**: Run all checks before pushing:
   ```bash
   uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
   ```
4. **Commit**: Use conventional commit messages
5. **Push**: Push to your branch
6. **Create PR**: Submit a pull request to the `dev` branch

### Automated Checks

When you create a pull request, CI/CD will automatically:

1. **Digital CLA Signature**: Contributors are expected to digitally sign a CLA in CI/CD
2. Run all linting checks (Ruff) - See [Lint Workflow](CI_CD.md#lint-workflow-githubworkflowslintyml)
3. Run type checking (Ty) - See [Lint Workflow](CI_CD.md#lint-workflow-githubworkflowslintyml)
4. Run full test suite with coverage requirements - See [Test Workflow](CI_CD.md#test-workflow-githubworkflowstestyml)
5. Run benchmark smoke tests - See [Benchmark Workflow](CI_CD.md#benchmark-workflow-githubworkflowsbenchmarkyml)
6. Build documentation - See [Documentation Workflow](CI_CD.md#documentation-workflow-githubworkflowsdocsyml)
7. Check code coverage thresholds - See [Coverage Requirements](CI_CD.md#coverage-requirements)

For detailed CI/CD documentation, see [CI/CD Documentation](CI_CD.md).

### Code Coverage

We maintain high code coverage standards. Coverage reports are generated and must meet minimum thresholds. View coverage reports in [reports/coverage.md](reports/coverage.md).

### Benchmark Requirements

Benchmark checks from [dev/pre-commit-config.yaml:39-68](https://github.com/yourusername/ccbittorrent/blob/main/dev/pre-commit-config.yaml#L39-L68) must pass. These include:

- Hash verification benchmarks
- Disk I/O benchmarks
- Piece assembly benchmarks
- Loopback throughput benchmarks

If benchmarks fail, the contribution may need optimization or discussion.

## Project Maintenance

### Automatic Acceptance

Contributions that pass all automated checks (linting, type checking, tests, benchmarks, coverage) are typically accepted automatically unless:

- Benchmarks fail (may require optimization)
- Conflicts with project direction (rare)
- Security concerns (handled separately)

### Manual Review

Maintainers may manually review for:
- Architecture alignment
- Performance implications
- Security considerations
- Documentation quality

## Documentation Standards

- All public APIs must be documented
- Use Google-style docstrings
- Keep documentation up-to-date with code changes
- Build documentation locally: `uv run mkdocs build --strict -f dev/mkdocs.yml`
- Documentation source is in [docs/](docs/)

## License

This project is licensed under the **GPL** (GNU General Public License). By contributing, you agree that your contributions will be licensed under the same license.

## Getting Help

- **Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and design discussions
- **Code Review**: All PRs receive code review from maintainers

## Recognition

Contributors are recognized for their valuable contributions. Significant contributions may be highlighted in release notes and project documentation.

Thank you for contributing to ccBitTorrent!
