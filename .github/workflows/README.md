# CI/CD Workflow Overview

This document provides a comprehensive overview of all GitHub Actions workflows in the ccBitTorrent project.

## Table of Contents

- [Testing & Quality Assurance](#testing--quality-assurance)
- [Build & Packaging](#build--packaging)
- [Release & Deployment](#release--deployment)

---

## Testing & Quality Assurance

### Test Workflow (test.yml)
- **Triggers**: Push/PR to `dev` branch, `workflow_dispatch`
- **Purpose**: Run full test suite with coverage across multiple platforms and Python versions
- **Runs**:
  - All tests except compatibility tests (excluded with `-m "not compatibility"`)
  - Coverage reporting (XML, HTML, terminal)
  - Test matrix: Ubuntu, Windows, macOS × Python 3.8-3.12 (reduced matrix for Windows/macOS)
- **Rationale**:
  - Tests run on `dev` branch (development branch), avoiding duplicate runs when merging to main
  - Excludes compatibility tests which run separately on schedule/manual trigger
  - Windows tests use `shell: bash` to handle line continuation correctly

### CI/CD Pipeline (ci.yml)
- **Triggers**: Push/PR to `main` and `dev` branches
- **Purpose**: Code quality checks (linting and type checking)
- **Runs**:
  - **Lint job**: Ruff linting with auto-fix and formatting checks
  - **Type-check job**: Ty type checking with concise output
- **Rationale**:
  - Ensures code quality before merging
  - Runs on both main and dev to catch issues early
  - Fast feedback loop for developers

### Compatibility Workflow (compatibility.yml)
- **Triggers**: 
  - Push to `main` branch
  - `workflow_dispatch` (manual)
- **Purpose**: Test compatibility across different environments and Python versions
- **Runs**:
  - **docker-test job**: Tests in Docker containers across Python 3.8-3.12 and OS variants (Ubuntu, Debian, Alpine)
  - **live-deployment-test job**: Builds package from wheel, tests installation, runs smoke tests (main branch only)
  - **compatibility-tests job**: Runs compatibility test suite (network tests, may be flaky)
- **Rationale**:
  - Ensures compatibility across different OS environments
  - Tests package installation and basic functionality
  - Compatibility tests are marked `continue-on-error: true` due to potential network flakiness

### Benchmark Workflow (benchmark.yml)
- **Triggers**:
  - Push to `main` branch (when code or performance tests change)
  - `workflow_dispatch` (manual)
- **Purpose**: Performance benchmarking and trend tracking
- **Runs**:
  - Hash verification benchmark
  - Disk I/O benchmark
  - Piece assembly benchmark
  - Loopback throughput benchmark
  - Encryption benchmark
- **Rationale**:
  - Tracks performance trends over time
  - Runs in `--quick` mode for CI speed
  - Automatically commits benchmark results to repository (main branch only)
  - Results stored in `docs/reports/benchmarks/`

### Security Workflow (security.yml)
- **Triggers**:
  - Push/PR to `main` branch
  - Weekly schedule
  - `workflow_dispatch` (manual)
- **Purpose**: Security scanning and vulnerability detection
- **Runs**:
  - Bandit security scanning (medium severity threshold)
  - Safety dependency vulnerability checking
- **Rationale**:
  - Regular security audits
  - Detects known vulnerabilities in dependencies
  - Weekly schedule ensures ongoing security monitoring

---

## Build & Packaging

### Build Workflow (build.yml)
- **Triggers**:
  - Push/PR to `main` branch
  - Tag push (`v*`)
  - `workflow_dispatch` (manual)
- **Purpose**: Build packages and executables
- **Runs**:
  - **build-package job**: Builds wheel and source distribution across Ubuntu, Windows, macOS
  - **build-windows-exe job**: Builds Windows executable (`bitonic.exe`) using PyInstaller (main branch or tags only)
- **Rationale**:
  - Validates package builds on all platforms
  - Creates distributable artifacts
  - Windows executable only built for releases (main branch or version tags)

### Documentation Workflow (build-documentation.yml)
- **Triggers**: `workflow_dispatch` (manual only)
- **Purpose**: Build documentation for testing and verification
- **Runs**:
  - Generate coverage report (for docs embedding)
  - Generate Bandit security report (for docs embedding)
  - Build documentation using patched build script
  - Upload documentation artifacts
- **Rationale**:
  - Manual trigger allows testing documentation builds from any branch
  - Documentation is automatically published to Read the Docs when changes are pushed
  - Coverage and Bandit reports are embedded in documentation
  - No GitHub Pages deployment (Read the Docs handles publishing)

---

## Release & Deployment

### Pre-Release Workflow (pre-release.yml)
- **Triggers**:
  - Pull request to `main` branch (when version files or CHANGELOG change)
  - `workflow_dispatch` (manual)
- **Purpose**: Pre-release validation and checklist reminders
- **Runs**:
  - **version-check job**: Verifies version consistency between `pyproject.toml` and `ccbt/__init__.py`
  - **release-checklist-reminder job**: Posts release checklist reminder in PR comments
- **Rationale**:
  - Catches version inconsistencies before merging
  - Ensures CHANGELOG is updated
  - Reminds maintainers of release checklist items

### Version Check Workflow (version-check.yml)
- **Triggers**:
  - Pull request to `main` or `dev` branches (when version files change)
  - Push to `main` or `dev` branches (when version files change)
  - Merge group events on `dev` branch
- **Purpose**: Continuous version consistency validation
- **Runs**:
  - Extracts version from `pyproject.toml` and `ccbt/__init__.py`
  - Verifies version consistency
  - Validates semantic versioning format
  - Validates branch-specific version rules:
    - `main` branch: version must be >= 0.1.0
    - `dev` branch: version must be > 0.0.0
  - Validates changelog
- **Rationale**:
  - Prevents version mismatches from being merged
  - Enforces semantic versioning standards
  - Branch-specific rules ensure proper versioning strategy

### Release to Main Workflow (release-to-main.yml)
- **Triggers**: `workflow_dispatch` (manual only)
- **Purpose**: Automated release process from dev to main branch
- **Runs**:
  - Accepts source branch input (default: `dev`)
  - Calculates new version (increments minor version, resets patch to 0)
  - Updates version in `pyproject.toml` and `ccbt/__init__.py`
  - Verifies version consistency
  - Commits version bump to main branch
  - Creates and pushes git tag (`v*`)
- **Rationale**:
  - Automates the release process
  - Ensures version consistency
  - Creates tags that trigger release workflow
  - Requires `contents: write` permission

### Release Workflow (release.yml)
- **Triggers**:
  - Tag push (`v*`)
  - `workflow_dispatch` (manual, requires version input)
- **Purpose**: Comprehensive pre-release validation and release creation
- **Runs**:
  - **pre-release-checks job**: Version validation, full test suite, linting, type checking, security scans
  - **build-docs job**: Documentation build validation
  - **create-release job**: Creates GitHub Release with automated release notes
- **Rationale**:
  - Ensures all quality gates pass before release
  - Comprehensive validation prevents broken releases
  - Automated release notes generation

### Publish Dev Branch to PyPI (publish-pypi-dev.yml)
- **Triggers**:
  - Push to `dev` branch (when code or version files change)
  - `workflow_dispatch` (manual)
- **Purpose**: Publish dev branch versions to PyPI as nightly builds
- **Runs**:
  - Validates version for dev branch (must be > 0.0.0)
  - Builds package
  - Publishes to PyPI using `uv publish`
  - Requires `PYPI_API_TOKEN` secret
- **Rationale**:
  - Allows users to test latest dev branch features
  - Nightly builds for continuous integration testing
  - Dev branch versions are marked as pre-release/nightly

### Publish to PyPI (publish-pypi.yml)
- **Triggers**:
  - Tag push (`v*`)
  - `workflow_dispatch` (manual, requires version input)
- **Purpose**: Publish stable releases to PyPI
- **Runs**:
  - Validates version for main branch (must be >= 0.1.0)
  - Builds package
  - Publishes to PyPI using `uv publish`
  - Verifies publication
  - Requires `PYPI_API_TOKEN` secret
- **Rationale**:
  - Publishes stable releases to PyPI
  - Only versions >= 0.1.0 are published (dev versions use separate workflow)
  - Verification step ensures package is available

### Deploy Workflow (deploy.yml)
- **Triggers**:
  - Release creation (GitHub release)
  - `workflow_dispatch` (manual, requires version input)
- **Purpose**: Production deployment to PyPI and GitHub Releases
- **Runs**:
  - **deploy-pypi job**:
    - Builds package
    - Publishes to PyPI using trusted publishing (OIDC)
    - Runs in `production` environment
  - **create-release-assets job**:
    - Downloads Windows executable artifact
    - Uploads package files and executable to GitHub Release
- **Rationale**:
  - Production deployment with trusted publishing (no tokens needed)
  - Creates complete release with all assets
  - Environment protection ensures only authorized deployments

---

## Workflow Dependencies

### Typical Release Flow

1. **Development** → Code changes on `dev` branch
2. **Testing** → `test.yml` runs on `dev` branch
3. **Version Check** → `version-check.yml` validates version consistency
4. **Release to Main** → `release-to-main.yml` bumps version and creates tag
5. **Release Validation** → `release.yml` runs comprehensive checks
6. **Build** → `build.yml` creates packages and executables
7. **Deploy** → `deploy.yml` publishes to PyPI and creates GitHub Release

### Documentation Flow

1. **Code Changes** → Documentation source files updated
2. **Manual Build** → `build-documentation.yml` can be triggered for testing
3. **Automatic Publish** → Read the Docs automatically builds and publishes when changes are pushed

### Continuous Quality

- **CI Pipeline** (`ci.yml`) runs on every push/PR for fast feedback
- **Version Check** (`version-check.yml`) ensures version consistency
- **Security** (`security.yml`) runs weekly and on main branch changes
- **Compatibility** (`compatibility.yml`) runs weekly and on main branch changes
- **Benchmarks** (`benchmark.yml`) track performance trends

---

## Workflow Permissions

All workflows now use explicit `permissions` blocks following the principle of least privilege. This ensures workflows only have the minimum permissions required.

### Workflows with Write Permissions

- **benchmark.yml**: `contents: write` (to commit benchmark results to repository)
- **release-to-main.yml**: `contents: write` (to commit version bumps and create tags)
- **release.yml** (create-release job): `contents: write` (to create GitHub releases)
- **deploy.yml**:
  - `deploy-pypi` job: `id-token: write` (for PyPI trusted publishing via OIDC), `production` environment
  - `create-release-assets` job: `contents: write` (to upload release assets)

### Workflows with Read-Only Permissions

All other workflows use read-only permissions:
- `contents: read` - Read repository contents
- `actions: read` - Read workflow run information
- `pull-requests: read` - Read pull request information (for PR-triggered workflows)

This includes: `test.yml`, `ci.yml`, `compatibility.yml`, `build.yml`, `build-documentation.yml`, `security.yml`, `pre-release.yml`, `version-check.yml`, `publish-pypi-dev.yml`, `publish-pypi.yml`

## Secrets Required

- **PYPI_API_TOKEN**: Required for `publish-pypi-dev.yml` and `publish-pypi.yml` (dev branch publishing)
- **Note**: `deploy.yml` uses trusted publishing (OIDC) and does not require PyPI token
