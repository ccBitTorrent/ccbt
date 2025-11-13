# CI/CD Implementation Plan for ccBitTorrent

**Repository**: https://github.com/ccBittorrent/ccbt  
**Target**: Complete CI/CD setup for first remote push with dev/main branch workflow

## Table of Contents

1. [Repository Configuration](#repository-configuration)
2. [Branch Strategy](#branch-strategy)
3. [Pre-Commit Integration](#pre-commit-integration)
4. [GitHub Actions Workflows](#github-actions-workflows)
5. [Testing Strategies](#testing-strategies)
6. [Build and Deployment](#build-and-deployment)
7. [Documentation](#documentation)
8. [Code Quality and Security](#code-quality-and-security)
9. [Issue Templates](#issue-templates)
10. [Badges and Status](#badges-and-status)
11. [Secrets and Keys](#secrets-and-keys)
12. [Compatibility Testing](#compatibility-testing)
13. [Tags and Releases](#tags-and-releases)
14. [Detailed File-Level TODOs](#detailed-file-level-todos)

---

## 1. Repository Configuration

### 1.1 Initial Repository Setup

**Activity**: Configure remote repository structure

**Tasks**:
- [ ] Create `dev` branch from `main`
- [ ] Set up branch protection rules
- [ ] Configure repository settings
- [ ] Set up repository topics/tags

**Subtasks**:

1. **Create dev branch**:
   ```bash
   git checkout -b dev
   git push -u origin dev
   ```

2. **Branch Protection Rules** (GitHub Settings → Branches):
   - **main branch**:
     - ✅ Require pull request reviews before merging
     - ✅ Require status checks to pass before merging
     - ✅ Require branches to be up to date before merging
     - ✅ Required status checks:
       - `test / ubuntu-latest, python-3.11`
       - `lint / ruff`
       - `lint / ty`
       - `security / bandit`
       - `coverage / codecov`
       - `build / package-check`
     - ✅ Restrict pushes that create files larger than 100MB
     - ✅ Do not allow bypassing the above settings
   
   - **dev branch**:
     - ✅ Require pull request reviews before merging (1 reviewer)
     - ✅ Require status checks to pass before merging
     - ✅ Required status checks:
       - `test / ubuntu-latest, python-3.11`
       - `lint / ruff`
       - `lint / ty`
     - ✅ Allow force pushes (for development flexibility)
     - ⚠️ Allow deletions (for cleanup)

3. **Repository Topics**:
   - `bittorrent`
   - `p2p`
   - `python`
   - `asyncio`
   - `torrent-client`
   - `high-performance`
   - `gpl-licensed`

4. **Repository Description**:
   ```
   High-performance BitTorrent client implementation in Python with async I/O, advanced piece selection, and comprehensive monitoring
   ```

---

## 2. Branch Strategy

### 2.1 Branch Workflow

**Activity**: Implement dev → main workflow

**Tasks**:
- [ ] Document branch strategy in CONTRIBUTING.md
- [ ] Configure GitHub branch rules
- [ ] Set up merge commit strategy

**Subtasks**:

1. **Merge Strategy** (GitHub Settings → General → Pull Requests):
   - Allow merge commits
   - Allow squash merging (for feature branches)
   - Allow rebase merging
   - Default to merge commit for `dev` → `main`

2. **Branch Naming Convention**:
   - Feature branches: `feature/description-issue-number`
   - Bug fixes: `fix/description-issue-number`
   - Hotfixes: `hotfix/description-issue-number`

---

## 3. Pre-Commit Integration

### 3.1 CI Pre-Commit Validation

**Activity**: Ensure pre-commit hooks run in CI

**Status**: ✅ Already configured in `dev/pre-commit-config.yaml`

**Tasks**:
- [ ] Verify pre-commit config is correct
- [ ] Test pre-commit hooks locally before push
- [ ] Document pre-commit setup in contributing guide

**File**: `dev/pre-commit-config.yaml` (already exists, verify)

**Verification**:
```bash
# Test locally before first push
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
```

---

## 4. GitHub Actions Workflows

### 4.1 Linting Workflow

**Activity**: Create workflow for code quality checks

**File**: `.github/workflows/lint.yml`

**Tasks**:
- [ ] Create lint workflow file
- [ ] Configure Ruff linting
- [ ] Configure Ty type checking
- [ ] Add Bandit security scanning
- [ ] Set up matrix for Python versions

**Implementation**:

```yaml
name: Lint

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  ruff:
    name: ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Run Ruff linting
        run: |
          uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
      
      - name: Run Ruff formatting check
        run: |
          uv run ruff --config dev/ruff.toml format --check ccbt/

  ty:
    name: ty
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Run Ty type checking
        run: |
          uv run ty check --config-file=dev/ty.toml --output-format=concise
```

**File-level TODO**:
- **Line 1-50**: Create `.github/workflows/lint.yml` with Ruff and Ty jobs

---

### 4.2 Testing Workflow

**Activity**: Create comprehensive test workflow

**File**: `.github/workflows/test.yml`

**Tasks**:
- [ ] Create test workflow with matrix strategy
- [ ] Configure pytest with coverage
- [ ] Set up Codecov integration
- [ ] Add test result artifacts
- [ ] Configure for dev and main branches

**Implementation**:

```yaml
name: Test

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  test:
    name: test
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
        exclude:
          # Reduce matrix size for faster CI
          - os: windows-latest
            python-version: '3.8'
          - os: windows-latest
            python-version: '3.9'
          - os: macos-latest
            python-version: '3.8'
          - os: macos-latest
            python-version: '3.9'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Run tests with coverage
        run: |
          uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=xml --cov-report=html --cov-report=term-missing
      
      - name: Upload coverage to Codecov
        if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.11'
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-umbrella
          token: ${{ secrets.CODECOV_TOKEN }}
          fail_ci_if_error: true
      
      - name: Upload test artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.os }}-py${{ matrix.python-version }}
          path: |
            coverage.xml
            htmlcov/
            site/reports/junit.xml
            site/reports/pytest.log
          retention-days: 7
```

**File-level TODO**:
- **Line 1-80**: Create `.github/workflows/test.yml` with matrix strategy
- **Line 45-50**: Configure Codecov upload with flags
- **Line 52-62**: Add artifact upload for test results

---

### 4.3 Security Workflow

**Activity**: Create security scanning workflow

**File**: `.github/workflows/security.yml`

**Tasks**:
- [ ] Create security workflow
- [ ] Configure Bandit scanning
- [ ] Add Safety dependency check
- [ ] Upload security reports

**Implementation**:

```yaml
name: Security

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
  schedule:
    # Run weekly on Mondays at 00:00 UTC
    - cron: '0 0 * * 1'

jobs:
  bandit:
    name: bandit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Ensure bandit directory exists
        run: |
          uv run python tests/scripts/ensure_bandit_dir.py
      
      - name: Run Bandit security scan
        run: |
          uv run bandit -r ccbt/ -f json -o docs/reports/bandit/bandit-report.json --severity-level medium -x tests,benchmarks,dev,dist,docs,htmlcov,site,.venv,.pre-commit-cache,.pre-commit-home,.pytest_cache,.ruff_cache,.hypothesis,.github,.ccbt,.cursor,.benchmarks
      
      - name: Upload Bandit report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: bandit-report
          path: docs/reports/bandit/bandit-report.json
          retention-days: 30
  
  safety:
    name: safety
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Run Safety check
        run: |
          uv run safety check --json
        continue-on-error: true
```

**File-level TODO**:
- **Line 1-70**: Create `.github/workflows/security.yml`
- **Line 25-30**: Configure Bandit with correct paths
- **Line 50-60**: Add Safety check job

---

### 4.4 Benchmark Workflow

**Activity**: Create benchmark recording workflow

**File**: `.github/workflows/benchmark.yml`

**Tasks**:
- [ ] Create benchmark workflow
- [ ] Configure benchmark recording
- [ ] Set up benchmark artifact storage
- [ ] Add benchmark comparison

**Implementation**:

```yaml
name: Benchmark

on:
  push:
    branches: [main, dev]
    paths:
      - 'ccbt/**'
      - 'tests/performance/**'
  workflow_dispatch:

jobs:
  benchmark:
    name: benchmark
    runs-on: ubuntu-latest
    if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for git metadata
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Run hash verification benchmark
        run: |
          uv run python tests/performance/bench_hash_verify.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
      
      - name: Run disk I/O benchmark
        run: |
          uv run python tests/performance/bench_disk_io.py --quick --sizes 256KiB 1MiB --record-mode=commit --config-file docs/examples/example-config-performance.toml
      
      - name: Run piece assembly benchmark
        run: |
          uv run python tests/performance/bench_piece_assembly.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
      
      - name: Run loopback throughput benchmark
        run: |
          uv run python tests/performance/bench_loopback_throughput.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
      
      - name: Run encryption benchmark
        run: |
          uv run python tests/performance/bench_encryption.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
      
      - name: Upload benchmark artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: |
            docs/reports/benchmarks/runs/*.json
            docs/reports/benchmarks/timeseries/*.json
          retention-days: 90
      
      - name: Commit benchmark results
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add docs/reports/benchmarks/
          git diff --staged --quiet || git commit -m "ci: record benchmark results [skip ci]"
          git push
```

**File-level TODO**:
- **Line 1-80**: Create `.github/workflows/benchmark.yml`
- **Line 30-55**: Configure all benchmark scripts with commit mode
- **Line 57-65**: Add artifact upload
- **Line 67-75**: Add auto-commit for main branch

---

### 4.5 Build Workflow

**Activity**: Create package build workflow

**File**: `.github/workflows/build.yml`

**Tasks**:
- [ ] Create build workflow
- [ ] Configure PyPI package building
- [ ] Add Windows executable building
- [ ] Set up artifact uploads

**Implementation**:

```yaml
name: Build

on:
  push:
    branches: [main]
    tags:
      - 'v*'
  pull_request:
    branches: [main]

jobs:
  build-package:
    name: build-package
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install build dependencies
        run: |
          uv sync --dev
          uv pip install build twine
      
      - name: Build package
        run: |
          uv run python -m build
      
      - name: Check package
        run: |
          uv run twine check dist/*
      
      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.os }}
          path: dist/*
          retention-days: 7

  build-windows-exe:
    name: build-windows-exe
    runs-on: windows-latest
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
          uv pip install pyinstaller
      
      - name: Build Windows executable (Terminal Dashboard only)
        run: |
          uv run pyinstaller --onefile --name bitonic --console ccbt/interface/terminal_dashboard.py
      
      - name: Upload Windows executable
        uses: actions/upload-artifact@v4
        with:
          name: windows-executable
          path: dist/bitonic.exe
          retention-days: 30
```

**File-level TODO**:
- **Line 1-70**: Create `.github/workflows/build.yml`
- **Line 25-40**: Configure package building with UV
- **Line 42-70**: Add Windows executable building with PyInstaller

---

### 4.6 Deploy Workflow

**Activity**: Create deployment workflow for PyPI and releases

**File**: `.github/workflows/deploy.yml`

**Tasks**:
- [ ] Create deploy workflow
- [ ] Configure PyPI publishing
- [ ] Set up GitHub Releases
- [ ] Add Windows executable to releases

**Implementation**:

```yaml
name: Deploy

on:
  release:
    types: [created]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to deploy (e.g., 0.1.0)'
        required: true
        type: string

jobs:
  deploy-pypi:
    name: deploy-pypi
    runs-on: ubuntu-latest
    environment: production
    permissions:
      contents: read
      id-token: write  # For trusted publishing
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install build dependencies
        run: |
          uv sync --dev
          uv pip install build twine
      
      - name: Build package
        run: |
          uv run python -m build
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/
          print-hash: true

  create-release-assets:
    name: create-release-assets
    runs-on: ubuntu-latest
    needs: deploy-pypi
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Download Windows executable
        uses: actions/download-artifact@v4
        with:
          name: windows-executable
          path: dist/
          github-token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Upload release assets
        uses: softprops/action-gh-release@v1
        with:
          files: dist/bitonic.exe
          draft: false
          prerelease: false
```

**File-level TODO**:
- **Line 1-60**: Create `.github/workflows/deploy.yml`
- **Line 30-45**: Configure PyPI trusted publishing
- **Line 47-60**: Add GitHub Release asset upload

---

### 4.7 Documentation Workflow

**Activity**: Create documentation build and deploy workflow

**File**: `.github/workflows/docs.yml`

**Tasks**:
- [ ] Create docs workflow
- [ ] Configure MkDocs build
- [ ] Set up GitHub Pages deployment
- [ ] Add documentation preview for PRs

**Implementation**:

```yaml
name: Documentation

on:
  push:
    branches: [main, dev]
    paths:
      - 'docs/**'
      - 'dev/mkdocs.yml'
      - 'ccbt/**'
  pull_request:
    branches: [main, dev]
    paths:
      - 'docs/**'
      - 'dev/mkdocs.yml'

jobs:
  build-docs:
    name: build-docs
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Generate coverage report
        run: |
          uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html:site/reports/htmlcov
        continue-on-error: true
      
      - name: Generate Bandit report
        run: |
          uv run python tests/scripts/ensure_bandit_dir.py
          uv run bandit -r ccbt/ -f json -o docs/reports/bandit/bandit-report.json --severity-level medium -x tests,benchmarks,dev,dist,docs,htmlcov,site,.venv,.pre-commit-cache,.pre-commit-home,.pytest_cache,.ruff_cache,.hypothesis,.github,.ccbt,.cursor,.benchmarks
        continue-on-error: true
      
      - name: Build documentation
        run: |
          uv run mkdocs build --strict -f dev/mkdocs.yml
      
      - name: Upload documentation artifact
        uses: actions/upload-artifact@v4
        with:
          name: documentation
          path: site/
          retention-days: 7
      
      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main'
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
          cname: ccbittorrent.readthedocs.io
```

**File-level TODO**:
- **Line 1-70**: Create `.github/workflows/docs.yml`
- **Line 30-40**: Add coverage report generation
- **Line 42-50**: Add Bandit report generation
- **Line 52-55**: Configure MkDocs build
- **Line 57-70**: Add GitHub Pages deployment

---

### 4.8 Compatibility Testing Workflow

**Activity**: Create containerized compatibility testing

**File**: `.github/workflows/compatibility.yml`

**Tasks**:
- [ ] Create compatibility workflow
- [ ] Set up Docker containers
- [ ] Configure multi-OS testing
- [ ] Add live deployment tests

**Implementation**:

```yaml
name: Compatibility

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
  schedule:
    # Run weekly on Sundays at 02:00 UTC
    - cron: '0 2 * * 0'

jobs:
  docker-test:
    name: docker-test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
        os-variant: ['ubuntu:20.04', 'ubuntu:22.04', 'debian:bullseye', 'alpine:3.18']
        exclude:
          - python-version: '3.8'
            os-variant: 'alpine:3.18'
          - python-version: '3.9'
            os-variant: 'alpine:3.18'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build test container
        run: |
          cat > dev/Dockerfile.test.tmp <<EOF
          FROM ${{ matrix.os-variant }}
          RUN apt-get update && apt-get install -y python${{ matrix.python-version }} python3-pip curl
          RUN curl -LsSf https://astral.sh/uv/install.sh | sh
          WORKDIR /app
          COPY . .
          RUN /root/.cargo/bin/uv sync --dev
          CMD ["/root/.cargo/bin/uv", "run", "pytest", "-c", "dev/pytest.ini", "tests/unit/", "-v"]
          EOF
      
      - name: Run tests in container
        run: |
          docker build -f dev/Dockerfile.test.tmp -t ccbt-test:${{ matrix.python-version }}-${{ matrix.os-variant }} .
          docker run --rm ccbt-test:${{ matrix.python-version }}-${{ matrix.os-variant }}

  live-deployment-test:
    name: live-deployment-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install UV
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          uv sync --dev
      
      - name: Build package
        run: |
          uv run python -m build
      
      - name: Install from wheel
        run: |
          uv pip install dist/*.whl
      
      - name: Test installation
        run: |
          ccbt --version
          btbt --version
          bitonic --version
      
      - name: Run smoke tests
        run: |
          uv run pytest -c dev/pytest.ini tests/integration/test_basic_download.py -v
```

**File-level TODO**:
- **Line 1-80**: Create `.github/workflows/compatibility.yml`
- **Line 20-50**: Configure Docker matrix testing
- **Line 52-80**: Add live deployment testing

---

## 5. Testing Strategies

### 5.1 Pre-Push Testing

**Activity**: Validate all checks before remote push

**Tasks**:
- [ ] Document local testing procedure
- [ ] Create test checklist
- [ ] Add pre-push validation script

**File**: `tests/scripts/pre_push_validation.sh`

**Implementation**:

```bash
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
```

**File-level TODO**:
- **Line 1-20**: Create `tests/scripts/pre_push_validation.sh`
- **Line 1**: Add shebang
- **Line 5-18**: Add validation steps

---

### 5.2 CI Testing Matrix

**Activity**: Ensure comprehensive test coverage

**Status**: Configured in `.github/workflows/test.yml`

**Coverage**:
- ✅ Python 3.8-3.12
- ✅ Ubuntu, Windows, macOS
- ✅ Unit tests
- ✅ Integration tests
- ✅ Coverage reporting

---

## 6. Build and Deployment

### 6.1 PyPI Package Configuration

**Activity**: Ensure pyproject.toml is PyPI-ready

**File**: `pyproject.toml` (already exists)

**Tasks**:
- [ ] Verify package metadata
- [ ] Update repository URLs
- [ ] Ensure license is correct
- [ ] Add PyPI-specific README

**File-level TODO**:
- **Line 6-7**: Update name and version
- **Line 12-14**: Update author information
- **Line 93-95**: Update repository URLs to `https://github.com/ccBittorrent/ccbt`
- **Line 11**: Verify license (currently MIT, should be GPL per contributing.md)

---

### 6.2 PyPI README

**Activity**: Create PyPI-specific README

**File**: `README_PyPI.md`

**Tasks**:
- [ ] Create PyPI README
- [ ] Focus on installation and usage
- [ ] Remove development-specific content
- [ ] Add PyPI badges

**File-level TODO**:
- **Line 1-100**: Create `docs/README_PyPI.md` with installation focus
- **Line 1-10**: Add PyPI badges (version, downloads)
- **Line 12-50**: Installation instructions
- **Line 52-80**: Basic usage examples
- **Line 82-100**: Quick links to full documentation

**Update pyproject.toml**:
- **Line 9**: Change `readme` to `readme = "docs/README_PyPI.md"`

---

### 6.3 Windows Executable Configuration

**Activity**: Configure PyInstaller for Windows builds (Terminal Dashboard only)

**File**: `dev/pyinstaller.spec` (new file, optional)

**Tasks**:
- [x] Create PyInstaller spec file (optional - can use command-line args)
- [x] Configure hidden imports for Textual dependencies
- [x] Set up icon and metadata
- [x] Optimize executable size

**Note**: The Windows executable is built only for the terminal dashboard (`bitonic`), not for the CLI tools (`ccbt`, `btbt`).

**File-level TODO**:
- [x] **Line 1-50**: Create `dev/pyinstaller.spec` for bitonic executable
- [x] **Line 1-20**: Configure analysis and hidden imports (Textual, Rich, etc.)
- [x] **Line 22-35**: Set up binaries and datas
- [x] **Line 37-50**: Configure EXE options

---

## 7. Documentation

### 7.1 MkDocs Configuration

**Activity**: Update MkDocs config for remote repository

**File**: `dev/mkdocs.yml` (already exists)

**Tasks**:
- [ ] Update repository URLs
- [ ] Configure GitHub Pages
- [ ] Update social links
- [ ] Verify plugin configuration

**File-level TODO**:
- **Line 6**: Update `repo_url` to `https://github.com/ccBittorrent/ccbt`
- **Line 7**: Update `repo_name` to `ccbt`
- **Line 76**: Update source link template URL
- **Line 118**: Update magiclink user/repo
- **Line 169**: Update GitHub social link

---

## 8. Code Quality and Security

### 8.1 Codecov Configuration

**Activity**: Update Codecov config for remote repository

**File**: `dev/.codecov.yml` (already exists)

**Tasks**:
- [ ] Verify coverage thresholds
- [ ] Ensure flags are correct
- [ ] Update for remote repository

**Status**: ✅ Configuration looks good, no changes needed

---

### 8.2 Bandit Configuration

**Activity**: Ensure Bandit is properly configured

**File**: `pyproject.toml` (already configured)

**Status**: ✅ Bandit configuration exists at lines 258-279

---

## 9. Issue Templates

### 9.1 Bug Report Template

**Activity**: Create bug report issue template

**File**: `.github/ISSUE_TEMPLATE/bug_report.md`

**Tasks**:
- [ ] Create bug report template
- [ ] Include environment details
- [ ] Add reproduction steps
- [ ] Include logs section

**File-level TODO**:
- **Line 1-50**: Create bug report template with all required fields

---

### 9.2 Feature Request Template

**Activity**: Create feature request template

**File**: `.github/ISSUE_TEMPLATE/feature_request.md`

**Tasks**:
- [ ] Create feature request template
- [ ] Add use case section
- [ ] Include implementation ideas
- [ ] Add related issues field

**File-level TODO**:
- **Line 1-40**: Create feature request template

---

### 9.3 User Experience Template

**Activity**: Create UX feedback template

**File**: `.github/ISSUE_TEMPLATE/user_experience.md`

**Tasks**:
- [ ] Create UX template
- [ ] Add interface section
- [ ] Include screenshots field
- [ ] Add improvement suggestions

**File-level TODO**:
- **Line 1-35**: Create UX feedback template

---

### 9.4 Compatibility Issue Template

**Activity**: Create compatibility issue template

**File**: `.github/ISSUE_TEMPLATE/compatibility_issue.md`

**Tasks**:
- [ ] Create compatibility template
- [ ] Add environment details
- [ ] Include OS/Python version
- [ ] Add error messages section

**File-level TODO**:
- **Line 1-45**: Create compatibility issue template

---

### 9.5 Issue Template Config

**Activity**: Create issue template configuration

**File**: `.github/ISSUE_TEMPLATE/config.yml`

**Tasks**:
- [ ] Create config file
- [ ] Configure template selection
- [ ] Add contact links

**File-level TODO**:
- **Line 1-30**: Create issue template configuration

---

## 10. Badges and Status

### 10.1 GitHub README Badges

**Activity**: Update README.md with correct badges

**File**: `.github/README.md` (GitHub repository README)

**Tasks**:
- [ ] Update Codecov badges with correct repository
- [ ] Add Bandit security badge
- [ ] Add feature badges
- [ ] Update build status badges

**File-level TODO**:
- **Line 3**: Update Codecov badge URL to `ccBittorrent/ccbt`
- **Line 4-6**: Update flag-specific Codecov badges
- **Line 7**: Add Bandit badge: `[![Bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)`
- **Line 8**: Add features badge section
- **Line 9**: Update license badge (currently GPL v2, verify)

**Badge Examples**:
```markdown
[![codecov](https://codecov.io/gh/ccBittorrent/ccbt/branch/main/graph/badge.svg)](https://codecov.io/gh/ccBittorrent/ccbt)
[![Bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![UV](https://img.shields.io/badge/package%20manager-uv-orange.svg)](https://github.com/astral-sh/uv)
```

---

### 10.2 PyPI README Badges

**Activity**: Add PyPI-specific badges

**File**: `docs/README_PyPI.md` (to be created)

**Tasks**:
- [ ] Add PyPI version badge
- [ ] Add download statistics
- [ ] Add Python version support
- [ ] Add license badge

**Badge Examples**:
```markdown
[![PyPI version](https://badge.fury.io/py/ccbt.svg)](https://badge.fury.io/py/ccbt)
[![Downloads](https://pepy.tech/badge/ccbt)](https://pepy.tech/project/ccbt)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
```

---

## 11. Secrets and Keys

### 11.1 Required GitHub Secrets

**Activity**: Document and configure required secrets

**Secrets to Add** (GitHub Settings → Secrets and variables → Actions):

1. **CODECOV_TOKEN**
   - **Purpose**: Code coverage reporting
   - **How to get**: 
     - Go to https://codecov.io
     - Sign in with GitHub
     - Add repository `ccBittorrent/ccbt`
     - Copy the upload token
   - **Where used**: `.github/workflows/test.yml` line 45

2. **PYPI_API_TOKEN** (for trusted publishing)
   - **Purpose**: PyPI package publishing
   - **How to get**:
     - Go to https://pypi.org/manage/account/
     - Create API token with "Entire account" scope
     - Or use trusted publishing (recommended)
   - **Where used**: `.github/workflows/deploy.yml` (if using API token)

3. **GITHUB_TOKEN** (automatically provided)
   - **Purpose**: GitHub API access
   - **Note**: Automatically available, no setup needed
   - **Where used**: All workflows for GitHub API access

**Tasks**:
- [ ] Set up Codecov account and add token
- [ ] Configure PyPI trusted publishing (preferred) or API token
- [ ] Verify secrets are accessible in workflows

---

### 11.2 Codecov Setup

**Activity**: Configure Codecov for the repository

**Steps**:
1. Go to https://codecov.io
2. Sign in with GitHub account
3. Add repository: `ccBittorrent/ccbt`
4. Copy upload token
5. Add token to GitHub Secrets as `CODECOV_TOKEN`
6. Verify `.codecov.yml` is in `dev/.codecov.yml` (already exists)

---

### 11.3 PyPI Trusted Publishing

**Activity**: Set up PyPI trusted publishing (recommended)

**Steps**:
1. Go to https://pypi.org/manage/account/publishing/
2. Add new pending publisher:
   - **PyPI project name**: `ccbt`
   - **Owner**: `ccBittorrent`
   - **Repository name**: `ccbt`
   - **Workflow filename**: `.github/workflows/deploy.yml`
   - **Environment name**: `production` (optional)
3. Approve the pending publisher
4. No token needed - uses OIDC

**Alternative**: If trusted publishing is not available, use API token:
- Create token at https://pypi.org/manage/account/token/
- Add as `PYPI_API_TOKEN` secret
- Update `.github/workflows/deploy.yml` to use token

---

## 12. Compatibility Testing

### 12.1 Docker Configuration

**Activity**: Create Dockerfiles for compatibility testing

**File**: `dev/Dockerfile.test.tmp` (temporary, generated in workflow)

**Status**: Generated dynamically in `.github/workflows/compatibility.yml`

**Alternative**: Create permanent Dockerfiles

**File**: `dev/Dockerfile.test` (permanent Dockerfile for local testing)

**Tasks**:
- [ ] Create base test Dockerfile
- [ ] Add multi-stage builds
- [ ] Configure for different Python versions

---

### 12.2 Docker Compose for Local Testing

**Activity**: Create docker-compose for local compatibility testing

**File**: `dev/docker-compose.test.yml`

**Tasks**:
- [ ] Create docker-compose file
- [ ] Configure test services
- [ ] Add volume mounts
- [ ] Set up test networks

**File-level TODO**:
- **Line 1-50**: Create `dev/docker-compose.test.yml` for local testing

---

## 13. Tags and Releases

### 13.1 Semantic Versioning

**Activity**: Implement semantic versioning strategy

**Version Format**: `vMAJOR.MINOR.PATCH`

**Examples**:
- `v0.1.0` - Initial release
- `v0.1.1` - Patch release (bug fixes)
- `v0.2.0` - Minor release (new features)
- `v1.0.0` - Major release (breaking changes)

**Tasks**:
- [ ] Document versioning strategy
- [ ] Create release checklist
- [ ] Set up automated release notes

---

### 13.2 Release Checklist

**Activity**: Create release process documentation

**File**: `docs/RELEASE_CHECKLIST.md`

**Tasks**:
- [ ] Create release checklist
- [ ] Document version bump process
- [ ] Add changelog update steps
- [ ] Include testing requirements

**File-level TODO**:
- **Line 1-100**: Create `docs/RELEASE_CHECKLIST.md` with complete process

---

### 13.3 Automated Release Notes

**Activity**: Configure automated release notes generation

**File**: `.github/release.yml`

**Tasks**:
- [ ] Create release configuration
- [ ] Configure changelog categories
- [ ] Set up auto-labeling

**File-level TODO**:
- **Line 1-50**: Create `.github/release.yml` for automated release notes

---

## 14. Detailed File-Level TODOs

### 14.1 Workflow Files

#### `.github/workflows/lint.yml`
- [ ] **Line 1**: Create file with name and on triggers
- [ ] **Line 10-30**: Add Ruff job with UV setup
- [ ] **Line 32-52**: Add Ty job with UV setup
- [ ] **Line 15**: Configure for `main` and `dev` branches

#### `.github/workflows/test.yml`
- [ ] **Line 1**: Create file with name and triggers
- [ ] **Line 10-25**: Configure matrix strategy (OS × Python)
- [ ] **Line 27-45**: Add UV setup and dependency installation
- [ ] **Line 47-50**: Configure pytest with coverage
- [ ] **Line 52-60**: Add Codecov upload (only for ubuntu-latest, py3.11)
- [ ] **Line 62-70**: Add artifact upload

#### `.github/workflows/security.yml`
- [ ] **Line 1**: Create file
- [ ] **Line 25-45**: Configure Bandit job
- [ ] **Line 47-65**: Configure Safety job
- [ ] **Line 30**: Ensure bandit directory script runs
- [ ] **Line 35**: Configure Bandit with correct paths

#### `.github/workflows/benchmark.yml`
- [ ] **Line 1**: Create file
- [ ] **Line 10**: Configure paths trigger for ccbt/ and tests/performance/
- [ ] **Line 30-55**: Add all benchmark script runs with commit mode
- [ ] **Line 57-65**: Configure artifact upload
- [ ] **Line 67-75**: Add auto-commit for main branch

#### `.github/workflows/build.yml`
- [x] **Line 1**: Create file
- [x] **Line 10**: Configure for main branch and tags
- [x] **Line 25-40**: Add package build job
- [x] **Line 42-70**: Add Windows executable build job (bitonic only)
- [x] **Line 50-65**: Configure PyInstaller with spec file support

#### `.github/workflows/deploy.yml`
- [x] **Line 1**: Create file
- [x] **Line 10**: Configure for release events
- [x] **Line 25-45**: Add PyPI deployment with trusted publishing
- [x] **Line 47-60**: Add GitHub Release asset upload
- [x] **Line 62-70**: Add post-deployment verification

#### `.github/workflows/docs.yml`
- [ ] **Line 1**: Create file
- [ ] **Line 30-40**: Add coverage report generation
- [ ] **Line 42-50**: Add Bandit report generation
- [ ] **Line 52-55**: Configure MkDocs build
- [ ] **Line 57-70**: Add GitHub Pages deployment

#### `.github/workflows/compatibility.yml`
- [ ] **Line 1**: Create file
- [ ] **Line 20-50**: Configure Docker matrix testing
- [ ] **Line 52-80**: Add live deployment testing

---

### 14.2 Configuration Files

#### `pyproject.toml`
- [ ] **Line 6**: Update package name if needed
- [ ] **Line 12-14**: Update author information
- [ ] **Line 93-95**: Update repository URLs to `https://github.com/ccBittorrent/ccbt`
- [ ] **Line 11**: Verify license (should be GPL per contributing.md, currently MIT)
- [ ] **Line 9**: Change readme to `README_PyPI.md` after creating it

#### `dev/mkdocs.yml`
- [ ] **Line 6**: Update `repo_url` to `https://github.com/ccBittorrent/ccbt`
- [ ] **Line 7**: Update `repo_name` to `ccbt`
- [ ] **Line 76**: Update source link template URL
- [ ] **Line 118**: Update magiclink user/repo to `ccBittorrent/ccbt`
- [ ] **Line 169**: Update GitHub social link

#### `README.md`
- [ ] **Line 3**: Update Codecov badge URL to `ccBittorrent/ccbt`
- [ ] **Line 4-6**: Update flag-specific Codecov badges
- [ ] **Line 7**: Add Bandit security badge
- [ ] **Line 8**: Add features badge section
- [ ] **Line 21**: Update clone URL to `https://github.com/ccBittorrent/ccbt.git`
- [ ] **Line 173**: Update clone URL in development section

#### `README_PyPI.md` (new file)
- [ ] **Line 1-10**: Create file with PyPI badges
- [ ] **Line 12-50**: Add installation instructions
- [ ] **Line 52-80**: Add basic usage examples
- [ ] **Line 82-100**: Add quick links to documentation

---

### 14.3 Issue Templates

#### `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] **Line 1-50**: Create bug report template

#### `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] **Line 1-40**: Create feature request template

#### `.github/ISSUE_TEMPLATE/user_experience.md`
- [ ] **Line 1-35**: Create UX feedback template

#### `.github/ISSUE_TEMPLATE/compatibility_issue.md`
- [ ] **Line 1-45**: Create compatibility issue template

#### `.github/ISSUE_TEMPLATE/config.yml`
- [ ] **Line 1-30**: Create issue template configuration

---

### 14.4 Additional Files

#### `dev/pyinstaller.spec` (new file)
- [x] **Line 1-50**: Create PyInstaller spec file for Windows executable (bitonic only)

#### `tests/scripts/pre_push_validation.sh` (new file)
- [ ] **Line 1-20**: Create pre-push validation script

#### `RELEASE_CHECKLIST.md` (new file)
- [ ] **Line 1-100**: Create release checklist document

#### `.github/release.yml` (new file)
- [x] **Line 1-50**: Create release configuration with changelog categories

#### `dev/docker-compose.test.yml` (optional)
- [x] **Line 1-50**: Create docker-compose for local testing
- [x] **Line 1-10**: Configure multiple Python version services
- [x] **Line 12-30**: Add integration test service
- [x] **Line 32-40**: Configure volumes and networks
- [x] **Line 7, 23, 39, 55, 71, 87**: Update dockerfile paths to `dev/Dockerfile.test`

---

## 15. Pre-Push Testing Checklist

Before pushing to remote for the first time:

### 15.1 Local Validation

- [ ] Run pre-commit hooks:
  ```bash
  uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
  ```

- [ ] Run linting:
  ```bash
  uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
  uv run ruff --config dev/ruff.toml format ccbt/
  ```

- [ ] Run type checking:
  ```bash
  uv run ty check --config-file=dev/ty.toml --output-format=concise
  ```

- [ ] Run tests:
  ```bash
  uv run pytest -c dev/pytest.ini tests/ -v
  ```

- [ ] Run tests with coverage:
  ```bash
  uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html --cov-report=xml
  ```

- [ ] Run security scan:
  ```bash
  uv run python tests/scripts/ensure_bandit_dir.py
  uv run bandit -r ccbt/ -f json -o docs/reports/bandit/bandit-report.json --severity-level medium
  ```

- [ ] Build documentation:
  ```bash
  uv run mkdocs build --strict -f dev/mkdocs.yml
  ```

- [ ] Test package build:
  ```bash
  uv run python -m build
  uv run twine check dist/*
  ```

---

### 15.2 Repository Configuration

- [ ] Create `dev` branch
- [ ] Set up branch protection rules for `main`
- [ ] Set up branch protection rules for `dev`
- [ ] Add repository topics
- [ ] Configure repository description
- [ ] Add Codecov token to secrets
- [ ] Configure PyPI trusted publishing (or add API token)
- [ ] Verify all workflow files are committed

---

### 15.3 First Push Sequence

1. **Push dev branch first**:
   ```bash
   git checkout dev
   git push -u origin dev
   ```

2. **Verify dev branch CI runs**:
   - Check GitHub Actions for dev branch
   - Verify all workflows pass
   - Check Codecov integration

3. **Create PR from dev to main**:
   - Create pull request in GitHub UI
   - Verify all status checks pass
   - Get code review approval

4. **Merge dev to main**:
   - Merge PR
   - Verify main branch CI runs
   - Check documentation deployment
   - Verify GitHub Pages is live

---

## 16. Post-Setup Verification

After initial setup, verify:

- [ ] All GitHub Actions workflows are green
- [ ] Codecov is reporting coverage
- [ ] Documentation is deployed to GitHub Pages
- [ ] Bandit reports are being generated
- [ ] Benchmarks are being recorded
- [ ] Issue templates are available
- [ ] Badges are displaying correctly
- [ ] Branch protection is active
- [ ] Secrets are configured correctly

---

## 17. Maintenance Tasks

### 17.1 Regular Maintenance

- [ ] Weekly: Review security scan results
- [ ] Weekly: Check benchmark trends
- [ ] Monthly: Review and update dependencies
- [ ] Per release: Update version numbers
- [ ] Per release: Generate changelog
- [ ] Per release: Create GitHub release

### 17.2 Monitoring

- [ ] Set up alerts for failed CI runs
- [ ] Monitor Codecov coverage trends
- [ ] Track benchmark performance regressions
- [ ] Review security scan results regularly

---

## Summary

This implementation plan provides:

1. ✅ **Complete workflow definitions** for all CI/CD processes
2. ✅ **Detailed file-level TODOs** for every file that needs creation/modification
3. ✅ **Testing strategies** before going live
4. ✅ **Branch strategy** with dev → main workflow
5. ✅ **Pre-commit integration** validation
6. ✅ **Benchmark recording** configuration
7. ✅ **PyPI package building** and deployment
8. ✅ **Windows executable** building
9. ✅ **Documentation deployment** with MkDocs
10. ✅ **Code quality** checks (Ruff, Ty, Bandit)
11. ✅ **Code coverage** reporting with Codecov
12. ✅ **Issue templates** for UX, bugs, compatibility, features
13. ✅ **Badges** for all relevant services
14. ✅ **Secrets configuration** guide
15. ✅ **Compatibility testing** with containers
16. ✅ **Tags and releases** strategy
17. ✅ **Release automation** with comprehensive checks
18. ✅ **CI/CD documentation** in `docs/CI_CD.md`

**Total Files to Create/Modify**: ~30 files
**Total Workflows**: 11 GitHub Actions workflows
**Estimated Setup Time**: 4-6 hours for complete implementation

## Documentation

Comprehensive CI/CD documentation is available in:
- **[docs/CI_CD.md](docs/CI_CD.md)** - Complete CI/CD system documentation
- **[docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md)** - Manual release process
- **[docs/contributing.md](docs/contributing.md)** - Development workflow with CI integration

---

## Next Steps

1. Review this plan
2. Create all workflow files
3. Update configuration files
4. Create issue templates
5. Set up GitHub repository settings
6. Configure secrets
7. Test locally with pre-push validation
8. Push dev branch
9. Verify CI runs
10. Create PR from dev to main
11. Merge and verify main branch CI
12. Celebrate! 🎉

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-XX  
**Author**: CI/CD Implementation Plan

