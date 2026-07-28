# CI/CD Workflow Overview

This document provides a comprehensive overview of all GitHub Actions workflows in the ccBitTorrent project.

**Policy**: All testing and builds run **manually** (via `workflow_dispatch`) for anything not targeting `main`. PRs to `main` run the same checks but **require manual approval** (environment `approval-required`) before jobs execute. See [Manual approval (approval-required)](#manual-approval-approval-required).

## Table of Contents

- [Manual approval (approval-required)](#manual-approval-approval-required)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Build & Packaging](#build--packaging)
- [Release & Deployment](#release--deployment)

---

## Manual approval (approval-required)

Workflows that run on **PR to main** use the environment **`approval-required`**. Before those jobs run, a configured reviewer must approve the run in the Actions UI.

**Setup**: In the repository go to **Settings → Environments → New environment** → name it `approval-required` → enable **Required reviewers** and add the users or teams who may approve runs. Jobs that reference this environment will then wait for approval before executing.

---

## Testing & Quality Assurance

### Test Workflow (test.yml)
- **Triggers**: PR to `main` (runs after approval), `workflow_dispatch`
- **Purpose**: Run full test suite with coverage across multiple platforms and Python versions
- **Runs**:
  - All tests except compatibility tests (excluded with `-m "not compatibility"`)
  - Coverage reporting (XML, HTML, terminal)
  - Test matrix: Ubuntu, Windows, macOS × Python 3.8-3.12 (reduced matrix for Windows/macOS)
- **Rationale**:
  - For branches other than `main`, run tests manually via **Actions → Test → Run workflow**
  - PRs to `main` trigger the workflow but require manual approval before jobs run

### CI/CD Pipeline (ci.yml)
- **Triggers**: PR to `main` (runs after approval), `workflow_dispatch`
- **Purpose**: Code quality checks (linting and type checking)
- **Runs**:
  - **Lint job**: Ruff linting with auto-fix and formatting checks
  - **Type-check job**: Ty type checking with concise output
- **Rationale**:
  - For branches other than `main`, run CI manually via **Actions → CI/CD Pipeline → Run workflow**
  - PRs to `main` require approval before lint/type-check jobs run

### Compatibility Workflow (compatibility.yml)
- **Triggers**: `workflow_dispatch` only (no PR/push triggers)
- **Purpose**: Test compatibility across different environments and Python versions
- **Runs**:
  - **docker-test job**: Tests in Docker containers across Python 3.8-3.12 and OS variants (Ubuntu, Debian, Alpine)
  - **live-deployment-test job**: Builds package from wheel, tests installation, runs smoke tests (main branch only)
  - **compatibility-tests job**: Runs compatibility test suite (network tests, may be flaky)
- **Rationale**:
  - Run manually when needed from **Actions → Compatibility → Run workflow**

### Benchmark Workflow (benchmark.yml)
- **Triggers**: `workflow_dispatch` and pull_request/PR paths updates
- **Purpose**: Performance benchmarking, baseline comparison, and trend tracking
- **Runs**:
  - Run benchmark suite for `head` changeset and compare against `base`
  - Evaluate deltas against `dev/benchmark_thresholds.toml`
  - Render committed docs from the comparison output and trend history
- **Rationale**:
  - Benchmarks stay out of pre-commit for faster local commits
  - PRs to `main` can validate regressions before merge
  - Commits only generated reports under `docs/en/reports/benchmarks/generated/`

### Security Workflow (security.yml)
- **Triggers**: PR to `main` (runs after approval), weekly schedule, `workflow_dispatch`
- **Purpose**: Security scanning and vulnerability detection
- **Runs**:
  - Bandit security scanning (medium severity threshold)
  - Safety dependency vulnerability checking
- **Rationale**:
  - PRs to `main` and scheduled runs use the `approval-required` environment

---

## Build & Packaging

### Build Workflow (build.yml)
- **Triggers**: `workflow_dispatch` only (all builds are manual)
- **Purpose**: Build packages and executables
- **Runs**:
  - **build-package job**: Builds wheel and source distribution across Ubuntu, Windows, macOS
  - **build-windows-exe job**: Builds Windows executable (`bitonic.exe`) using PyInstaller when run from `main`
- **Rationale**:
  - No automatic build on push or tags; run from **Actions → Build → Run workflow** when needed

### Documentation Workflow (build-documentation.yml)
- **Triggers**: PR to `main` (runs after approval), `workflow_dispatch`
- **Purpose**: Build documentation for testing and verification
- **Runs**:
  - Waits for CI/CD Pipeline and Test workflow runs to succeed for the PR head SHA
  - Generate coverage report (for docs embedding)
  - Generate Bandit security report (for docs embedding)
  - Build documentation using patched build script
  - Upload documentation artifacts
- **Rationale**:
  - PRs to `main` trigger the workflow but require approval; or run manually from any branch
  - Validation gate polls instead of failing while Test/CI are still in progress

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
- **Triggers**: PR to `main` (when version files change, runs after approval), `workflow_dispatch`
- **Purpose**: Version consistency validation
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
- **Triggers**: PR to `main` (runs after approval), `workflow_dispatch`
- **Purpose**: Publish to PyPI as nightly builds
- **Runs**:
  - Waits for CI/CD Pipeline and Test workflow runs to succeed for the PR head SHA (polls; does not fail while they are still running)
  - Builds package and publishes to PyPI using `uv publish`
  - Requires `PYPI_API_TOKEN` secret
- **Rationale**:
  - Nightly publish is manual by default; on PR to main it can run after approval
  - Requires `approval-required` environment to be configured

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
    - Runs in `pypi` environment (GitHub Environment for trusted publishing)
  - **create-release-assets job**:
    - Downloads Windows executable artifact
    - Uploads package files and executable to GitHub Release
- **Rationale**:
  - Production deployment with trusted publishing (no tokens needed)
  - Creates complete release with all assets
  - Environment protection ensures only authorized deployments
- **Setup**: Create the **`pypi`** environment so the deploy job can run and IDE validation passes: **Settings → Environments → New environment** → name it `pypi`. Configure [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) with this repository and environment name. Optionally enable **Required reviewers** for the `pypi` environment to gate production publishes.

---

## Workflow Dependencies

### Typical Release Flow

1. **Development** → Code changes on `dev` (or feature branches)
2. **Testing** → Run `test.yml` and `ci.yml` manually, or open PR to `main` and get approval to run checks
3. **Version Check** → Run `version-check.yml` manually or as part of PR to `main` (after approval)
4. **Release to Main** → `release-to-main.yml` bumps version and creates tag (manual)
5. **Release Validation** → `release.yml` runs comprehensive checks
6. **Build** → `build.yml` run manually to create packages and executables
7. **Deploy** → `deploy.yml` publishes to PyPI and creates GitHub Release

### Documentation Flow

1. **Code Changes** → Documentation source files updated
2. **Build** → Run `build-documentation.yml` manually or via PR to `main` (after approval)
3. **Publish** → Read the Docs builds from the repository when configured

### Continuous Quality

- **CI Pipeline** (`ci.yml`) and **Test** (`test.yml`): PR to `main` (with approval) or manual run
- **Version Check** (`version-check.yml`): PR to `main` (with approval) or manual run
- **Security** (`security.yml`): PR to `main` (with approval), weekly schedule, or manual run
- **Compatibility** (`compatibility.yml`): manual run only
- **Benchmark** (`benchmark.yml`): manual run and pull_request flow as defined in the workflow

---

## Workflow Permissions

All workflows now use explicit `permissions` blocks following the principle of least privilege. This ensures workflows only have the minimum permissions required.

### Workflows with Write Permissions

- **benchmark.yml**: `contents: write` (to commit benchmark results to repository)
- **release-to-main.yml**: `contents: write` (to commit version bumps and create tags)
- **release.yml** (create-release job): `contents: write` (to create GitHub releases)
- **deploy.yml**:
  - `deploy-pypi` job: `id-token: write` (for PyPI trusted publishing via OIDC), `pypi` environment
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
