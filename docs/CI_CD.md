# CI/CD Documentation

This document describes the Continuous Integration and Continuous Deployment (CI/CD) setup for ccBitTorrent.

## Overview

ccBitTorrent uses GitHub Actions for automated testing, building, and deployment. The CI/CD pipeline ensures code quality, comprehensive testing, and automated releases.

## Workflow Overview

### Core Workflows

1. **Lint** (`.github/workflows/lint.yml`) - Code quality checks
2. **Test** (`.github/workflows/test.yml`) - Comprehensive test suite
3. **Security** (`.github/workflows/security.yml`) - Security scanning
4. **Benchmark** (`.github/workflows/benchmark.yml`) - Performance benchmarks
5. **Build** (`.github/workflows/build.yml`) - Package and executable building
6. **Deploy** (`.github/workflows/deploy.yml`) - PyPI and GitHub Releases
7. **Documentation** (`.github/workflows/docs.yml`) - Documentation build and deployment
8. **Compatibility** (`.github/workflows/compatibility.yml`) - Containerized testing

### Release Workflows

9. **Release** (`.github/workflows/release.yml`) - Automated release process
10. **Pre-Release** (`.github/workflows/pre-release.yml`) - Pre-release validation
11. **Version Check** (`.github/workflows/version-check.yml`) - Version consistency

## Testing in CI

### Test Workflow (`.github/workflows/test.yml`)

The test workflow runs the full test suite across multiple platforms and Python versions.

#### Test Matrix

- **Operating Systems**: Ubuntu, Windows, macOS
- **Python Versions**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Exclusions**: Reduced matrix for faster CI (Windows/macOS skip 3.8/3.9)

#### Test Execution

```yaml
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=xml --cov-report=html --cov-report=term-missing
```

#### Coverage Reporting

- Coverage is uploaded to Codecov from the primary test job (Ubuntu + Python 3.11)
- Coverage reports are generated in XML, HTML, and terminal formats
- Coverage thresholds are enforced:
  - **Project**: 99% (±1%)
  - **Patch**: 90% (±2%)

#### Test Artifacts

Test artifacts are uploaded for debugging:
- `coverage.xml` - Codecov-compatible coverage report
- `htmlcov/` - HTML coverage report
- `site/reports/junit.xml` - JUnit XML test results
- `site/reports/pytest.log` - Test execution logs

### Integration with Testing Patterns

The CI workflows respect the testing patterns defined in the project:

#### Test Markers

CI runs all tests without marker filtering, ensuring comprehensive coverage. The test suite includes:

- **Unit tests** (`tests/unit/`) - Individual component testing
- **Integration tests** (`tests/integration/`) - Component workflow testing
- **Property-based tests** (`tests/property/`) - Hypothesis-based testing
- **Performance tests** (`tests/performance/`) - Benchmark validation
- **Chaos tests** (`tests/chaos/`) - Resilience testing

#### Async Testing

All async tests run with `asyncio_mode = auto` as configured in `dev/pytest.ini`. The CI environment properly handles async test execution.

#### Timeouts

Tests use default timeouts (300s per test) as configured in pytest. Coverage runs use extended timeouts (600s) to handle comprehensive test suites.

### Pre-Commit vs CI

**Pre-commit hooks** (local development):
- Run selective tests based on changed files
- Use `tests/scripts/run_pytest_selective.py` for efficient local testing
- Fast feedback loop for developers

**CI workflows** (remote validation):
- Run full test suite across all platforms
- Comprehensive coverage reporting
- Platform-specific validation

## Code Quality Checks

### Lint Workflow (`.github/workflows/lint.yml`)

Runs code quality checks:

1. **Ruff Linting**
   ```bash
   uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
   ```

2. **Ruff Formatting**
   ```bash
   uv run ruff --config dev/ruff.toml format --check ccbt/
   ```

3. **Ty Type Checking**
   ```bash
   uv run ty check --config-file=dev/ty.toml --output-format=concise
   ```

### Security Workflow (`.github/workflows/security.yml`)

Runs security scanning:

1. **Bandit Security Scan**
   - Scans for common security issues
   - Generates JSON report to `docs/reports/bandit/bandit-report.json`
   - Medium severity threshold

2. **Safety Dependency Check**
   - Checks for known vulnerabilities in dependencies
   - Runs weekly on schedule

## Performance Benchmarks

### Benchmark Workflow (`.github/workflows/benchmark.yml`)

Runs performance benchmarks on code changes:

- **Hash Verification Benchmark** - SHA-1 verification performance
- **Disk I/O Benchmark** - File read/write performance
- **Piece Assembly Benchmark** - Piece reconstruction performance
- **Loopback Throughput Benchmark** - Network throughput
- **Encryption Benchmark** - Cryptographic operations

Benchmarks run in `--quick` mode for CI and record results for trend analysis.

## Build and Deployment

### Build Workflow (`.github/workflows/build.yml`)

Builds packages and executables:

1. **Package Building**
   - Builds wheel and source distributions
   - Validates packages with `twine check`
   - Runs on Ubuntu, Windows, and macOS

2. **Windows Executable**
   - Builds `bitonic.exe` (terminal dashboard) using PyInstaller
   - Uses `dev/pyinstaller.spec` if available, otherwise command-line args
   - Only builds on Windows runners
   - Uploads as artifact for release

### Deploy Workflow (`.github/workflows/deploy.yml`)

Deploys to PyPI and creates GitHub Releases:

1. **PyPI Deployment**
   - Uses trusted publishing (OIDC) - no tokens needed
   - Validates package before publishing
   - Verifies publication after upload

2. **GitHub Release**
   - Downloads Windows executable artifact
   - Uploads package files and executable to release
   - Creates release with automated notes

## Release Process

### Release Workflow (`.github/workflows/release.yml`)

Automated release process triggered by version tags (`v*`):

#### Pre-Release Checks

1. **Code Quality**
   - Linting (Ruff)
   - Type checking (Ty)
   - Security scan (Bandit)

2. **Testing**
   - Full test suite with coverage
   - Coverage threshold check (99%)
   - Package installation test

3. **Documentation**
   - MkDocs build validation
   - Documentation completeness check

4. **Build Verification**
   - Package build and validation
   - Windows executable build (if applicable)

#### Release Creation

1. **Version Extraction** - Extracts version from Git tag
2. **Release Notes Generation**
   - Reads from `CHANGELOG.md` if available
   - Falls back to commit history since last tag
   - Includes installation instructions
3. **GitHub Release** - Creates release with assets

#### Post-Release Verification

1. **PyPI Verification** - Tests package installation from PyPI
2. **Release Verification** - Confirms GitHub Release creation
3. **Documentation Verification** - Confirms documentation deployment

### Pre-Release Workflow (`.github/workflows/pre-release.yml`)

Validates release readiness for PRs to `main`:

1. **Version Consistency**
   - Checks `pyproject.toml` vs `ccbt/__init__.py`
   - Validates semantic versioning format

2. **CHANGELOG Check**
   - Verifies CHANGELOG.md contains version entry
   - Provides reminders for missing entries

3. **Release Checklist Reminder**
   - Posts checklist summary in PR comments
   - Links to `docs/RELEASE_CHECKLIST.md`

### Version Check Workflow (`.github/workflows/version-check.yml`)

Validates version consistency on version file changes:

- Checks `pyproject.toml` version matches `ccbt/__init__.py`
- Validates semantic versioning format
- Fails CI if versions are inconsistent

## Documentation

### Documentation Workflow (`.github/workflows/docs.yml`)

Builds and deploys documentation:

1. **Coverage Report Generation**
   - Generates HTML coverage report
   - Integrates with MkDocs via `mkdocs-coverage` plugin

2. **Bandit Report Generation**
   - Generates security scan report
   - Includes in documentation

3. **MkDocs Build**
   - Builds documentation site
   - Validates with `--strict` mode

4. **GitHub Pages Deployment**
   - Deploys to GitHub Pages on `main` branch
   - Uses custom domain: `ccbittorrent.readthedocs.io`

## Compatibility Testing

### Compatibility Workflow (`.github/workflows/compatibility.yml`)

Tests compatibility across environments:

1. **Docker Testing**
   - Tests on multiple OS variants (Ubuntu, Debian, Alpine)
   - Tests on Python 3.8-3.12
   - Runs unit tests in containers

2. **Live Deployment Test**
   - Builds package from wheel
   - Tests installation
   - Runs smoke tests

3. **Schedule**
   - Runs weekly on Sundays at 02:00 UTC
   - Ensures ongoing compatibility

### Local Docker Testing

For local compatibility testing, use the Docker Compose configuration:

```bash
docker-compose -f dev/docker-compose.test.yml up
```

This runs tests across Python 3.8-3.12 and integration tests. The Dockerfile is located at `dev/Dockerfile.test`.

## Branch Strategy

### Main Branch

- **Purpose**: Production releases
- **Protection**: Requires PR reviews and status checks
- **CI**: Full test suite, builds, documentation deployment
- **Releases**: Automatic on version tags

### Dev Branch

- **Purpose**: Development integration
- **CI**: Full test suite (same as main)
- **Merges**: Only branch that merges to main
- **Benchmarks**: All benchmark checks run

### Feature Branches

- **CI**: Full test suite on PR
- **Selective Testing**: Pre-commit hooks use selective testing locally
- **Merges**: To `dev` branch

## Coverage Requirements

### Codecov Integration

Coverage is tracked via Codecov with the following targets:

- **Project Coverage**: 99% (±1% tolerance)
- **Patch Coverage**: 90% (±2% tolerance)

### Coverage Flags

Coverage is categorized by domain using flags (from `dev/.codecov.yml`):

- `unittests` - Unit test coverage
- `security` - Security-related code coverage
- `ml` - Machine learning features coverage
- `core` - Core BitTorrent functionality
- `peer` - Peer management
- `piece` - Piece management
- `tracker` - Tracker communication
- `network` - Network layer
- `metadata` - Metadata handling
- `disk` - Disk I/O operations
- `file` - File operations
- `session` - Session management
- `resilience` - Resilience features

## Secrets and Configuration

### Required Secrets

1. **CODECOV_TOKEN**
   - Purpose: Code coverage reporting
   - Setup: https://codecov.io → Add repository → Copy token

2. **PyPI Trusted Publishing** (Recommended)
   - Purpose: PyPI package publishing
   - Setup: https://pypi.org/manage/account/publishing/
   - No token needed - uses OIDC

### Environment Variables

- `GITHUB_TOKEN` - Automatically provided by GitHub Actions
- `CCBT_TEST_SEED` - Test RNG seed (default: 123456)

## Workflow Triggers

### Push Events

- **main/dev branches**: All workflows run
- **Feature branches**: Test, lint, security workflows run

### Pull Request Events

- **To main/dev**: All validation workflows run
- **Version files changed**: Version check workflow runs

### Tag Events

- **Version tags (v*)**: Release workflow runs
- **Release created**: Deploy workflow runs

### Schedule Events

- **Security**: Weekly on Mondays at 00:00 UTC
- **Compatibility**: Weekly on Sundays at 02:00 UTC

## Artifacts and Reports

### Test Artifacts

- Coverage reports (XML, HTML)
- Test results (JUnit XML)
- Test logs

### Build Artifacts

- Package distributions (wheel, source)
- Windows executable (`bitonic.exe`)

### Benchmark Artifacts

- Benchmark results (JSON)
- Time series data
- Performance trends

### Documentation Artifacts

- Built documentation site
- Coverage HTML reports
- Bandit security reports

## Troubleshooting

### CI Failures

1. **Test Failures**
   - Check test artifacts for detailed logs
   - Review coverage reports for missing coverage
   - Ensure tests are deterministic (use fixtures)

2. **Coverage Failures**
   - Review Codecov report for specific files
   - Ensure new code has tests
   - Check coverage thresholds in `dev/.codecov.yml`

3. **Build Failures**
   - Check build logs for dependency issues
   - Verify `pyproject.toml` is valid
   - Ensure all dependencies are available

4. **Release Failures**
   - Verify version consistency
   - Check CHANGELOG.md exists and is updated
   - Ensure all pre-release checks pass

### Local Testing

Before pushing, run locally:

```bash
# Run all checks
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml

# Run full test suite
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=term-missing

# Build package
uv run python -m build
uv run twine check dist/*
```

## Best Practices

1. **Run Pre-Commit Hooks Locally** - Catch issues before CI
2. **Write Tests for New Code** - Maintain coverage thresholds
3. **Update CHANGELOG.md** - Document changes for releases
4. **Follow Semantic Versioning** - Use MAJOR.MINOR.PATCH format
5. **Test Locally First** - Reduce CI failures and feedback time

## Related Documentation

- [Testing Patterns](testing-patterns) - Testing requirements and patterns
- [Release Checklist](RELEASE_CHECKLIST.md) - Manual release process
- [Contributing Guide](contributing.md) - Development workflow
- [Configuration](configuration.md) - Project configuration

---

**Last Updated**: 2025-01-XX  
**Maintained By**: CI/CD Team

