# CI/CD Workflow Reorganization Plan (Improved)

## Executive Summary

This plan comprehensively addresses CI/CD workflow issues with **proper sequencing, dependency management, and concurrency controls** to prevent race conditions and ensure checks run before writes.

**Key Improvements:**
- ✅ **No verifications on push** - All checks run on PRs to dev only
- ✅ **Compatibility tests** manual only (very expensive and time-consuming)
- ✅ **Proper job dependencies and sequencing** using `needs:` and `workflow_call`
- ✅ **Concurrency controls** to prevent race conditions on write operations
- ✅ **Dev branch**: Nightly PyPI publishes available on PRs/pushes but require validation and manual trigger
- ✅ **Main branch**: Releases available on PRs/pushes but require validation and manual trigger (with automatic version bumping)
- ✅ **Documentation builds** on push to main (automatic) or available on PRs with validation requirement
- ✅ **Reports generation** always manual, never automatic
- ✅ **Builds** on push to main or manual only (not on PRs)
- ✅ **Version bumping** uses existing scripts (`validate_version.py`) and logic
- ✅ **All write operations** properly sequenced and protected

---

## Critical Issues Identified

### Race Conditions
1. **Multiple workflows committing simultaneously**: `benchmark.yml` and `release-to-main.yml` can both commit to main at the same time
2. **Documentation build before reports**: `build-documentation.yml` might run before reports are generated
3. **No concurrency controls**: No `concurrency:` groups to prevent parallel writes

### Ordering Issues
1. **Verifications run on push**: Should only run on PRs to dev
2. **Reports generation automatic**: Should always be manual
3. **Releases automatic**: Should always be manual (with different behavior for dev vs main)
4. **Version bumping not using scripts**: Should use existing `validate_version.py` script

### Write Operations Analysis
1. **benchmark.yml** (Line 70-77): Commits benchmark results to main
2. **release-to-main.yml** (Line 97-108): Commits version bumps and merges
3. **build-documentation.yml**: Generates reports inline (no commits, but writes to site/)
4. **Scripts called**: All read-only except `build_docs_patched_clean.py` (writes to site/)

---

## Priority 0: Critical Fixes (Blocks All Operations)

### PROJECT 1: Add Concurrency Controls
**Priority**: P0 - Critical  
**Goal**: Prevent race conditions on write operations

#### Activity 1.1: Add concurrency groups to write workflows
**File**: `.github/workflows/benchmark.yml`

**Task 1.1.1**: Add concurrency control
- **After line 10**: Add concurrency group:
  ```yaml
  concurrency:
    group: benchmark-write-${{ github.ref }}
    cancel-in-progress: false  # Don't cancel, queue instead
  ```

**File**: `.github/workflows/release-to-main.yml`

**Task 1.1.2**: Add concurrency control
- **After line 11**: Add concurrency group:
  ```yaml
  concurrency:
    group: release-to-main
    cancel-in-progress: false
  ```

**File**: `.github/workflows/build-documentation.yml`

**Task 1.1.3**: Add concurrency control
- **After line 22**: Add concurrency group:
  ```yaml
  concurrency:
    group: docs-build-${{ github.ref }}
    cancel-in-progress: false
  ```

---

### PROJECT 2: Fix Compatibility Tests
**Priority**: P0 - Critical  
**Goal**: Compatibility tests should be available on PRs/pushes but require validation and be manually triggered (very expensive and time-consuming)

#### Activity 2.1: Update compatibility.yml to be available but require validation
**File**: `.github/workflows/compatibility.yml`

**Task 2.1.1**: Add PR and push triggers (makes workflow available), but require validation
- **Line 3-6**: Replace with:
  ```yaml
  on:
    pull_request:
      branches: [dev, main]  # Available on PRs but not automatic
    push:
      branches: [dev, main]  # Available on pushes but not automatic
    workflow_dispatch:  # Manual trigger
    workflow_run:  # Trigger after validation workflows pass
      workflows: ["CI/CD Pipeline", "Test"]
      types:
        - completed
      branches: [dev, main]
  ```

**Task 2.1.2**: Add validation check job that must pass first
- **After line 7**, add new job:
  ```yaml
  jobs:
    check-validation:
      name: check-validation
      runs-on: ubuntu-latest
      if: |
        github.event_name == 'workflow_dispatch' ||
        (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success')
      steps:
        - name: Check if validation workflows passed
          uses: actions/github-script@v7
          with:
            script: |
              // For PRs, check if ci.yml and test.yml have passed
              if (context.eventName === 'pull_request') {
                const { data: checks } = await github.rest.checks.listForRef({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  ref: context.payload.pull_request.head.sha,
                });
                const requiredChecks = ['CI/CD Pipeline', 'Test'];
                const passedChecks = checks.check_runs.filter(
                  check => requiredChecks.includes(check.name) && check.conclusion === 'success'
                );
                if (passedChecks.length < requiredChecks.length) {
                  core.setFailed('Required validation workflows must pass first');
                }
              }
              // For workflow_run, validation already passed
              // For workflow_dispatch, allow manual override
    docker-test:
      name: docker-test
      needs: check-validation
      if: |
        github.event_name == 'workflow_dispatch' ||
        (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') ||
        (github.event_name == 'pull_request' && needs.check-validation.result == 'success')
  ```

**Task 2.1.3**: Update existing job conditions
- **Line 47**: Change to:
  ```yaml
  if: |
    github.event_name == 'workflow_dispatch' ||
    (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') ||
    (github.event_name == 'pull_request' && needs.check-validation.result == 'success')
  ```
- **Line 89-93**: Change to:
  ```yaml
  if: |
    github.event_name == 'workflow_dispatch' ||
    (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') ||
    (github.event_name == 'pull_request' && needs.check-validation.result == 'success')
  ```

---

### PROJECT 3: Fix release-to-main.yml
**Priority**: P0 - Critical  
**Goal**: Actually merge code from dev to main, then bump version using existing logic

#### Activity 3.1: Add merge logic with proper sequencing
**File**: `.github/workflows/release-to-main.yml`

**Task 3.1.1**: Add merge step before version bump
- **After line 70** (after checkout main), add:
  ```yaml
  - name: Merge dev into main
    run: |
      git fetch origin dev
      # Check if merge is needed
      if git merge-base --is-ancestor origin/dev HEAD; then
        echo "✅ Dev is already merged into main"
      else
        git merge origin/dev --no-ff -m "chore: merge dev into main for release [skip ci]"
        git push origin main || {
          echo "⚠️  Push failed (may need manual merge)"
          exit 1
        }
      fi
  ```

**Task 3.1.2**: Add version validation using existing script
- **After line 31** (after configure git), add:
  ```yaml
  - name: Validate version using script
    run: |
      uv run python dev/scripts/validate_version.py || exit 1
  ```

**Task 3.1.3**: Ensure proper sequencing
- **Line 32-51**: Version extraction happens after merge
- **Line 97-101**: Version bump commit happens after merge
- **Line 103-108**: Tag creation happens after version bump

---

## Priority 1: Build and Release Automation

### PROJECT 5: Fix Build Workflows
**Priority**: P1 - High  
**Goal**: Builds should only happen on push to main or manual, not on PRs

#### Activity 4.1: Update build.yml triggers
**File**: `.github/workflows/build.yml`

**Task 4.1.1**: Remove PR trigger, keep push to main and manual
- **Line 3-10**: Change to:
  ```yaml
  on:
    push:
      branches: [main]
      tags:
        - 'v*'
    workflow_dispatch:  # Manual only, no PR trigger
  ```

**Task 4.1.2**: Add concurrency control
- **After line 11**: Add:
  ```yaml
  concurrency:
    group: build-${{ github.ref }}
    cancel-in-progress: false
  ```

---

### PROJECT 6: Fix Windows .exe Build
**Priority**: P1 - High  
**Goal**: Ensure Windows executable builds correctly and doesn't skip

#### Activity 5.1: Fix build condition and add dependencies
**File**: `.github/workflows/build.yml`

**Task 5.1.1**: Verify condition and add job dependency
- **Line 57-60**: Condition is correct, but add dependency:
  ```yaml
  build-windows-exe:
    name: build-windows-exe
    runs-on: windows-latest
    needs: build-package  # Wait for package build first
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')
  ```

**Task 5.1.2**: Add error handling
- **Line 82-98**: Add verification and error handling:
  ```yaml
  - name: Build Windows executable (Terminal Dashboard only)
    shell: pwsh
    run: |
      # Use spec file if it exists, otherwise use command-line args
      if (Test-Path dev/pyinstaller.spec) {
        uv run pyinstaller --clean dev/pyinstaller.spec
      } else {
        uv run pyinstaller --onefile --name bitonic --console ccbt/interface/terminal_dashboard.py
      }
      
      # Verify executable was created
      if (-not (Test-Path dist/bitonic.exe)) {
        Write-Error "Error: bitonic.exe was not created"
        Get-ChildItem dist/ -Recurse | Select-Object FullName
        exit 1
      }
      
      Write-Host "✅ Windows executable built successfully: dist/bitonic.exe"
      Get-Item dist/bitonic.exe | Select-Object Name, Length, LastWriteTime
  ```

---

### PROJECT 7: Fix Release Workflows
**Priority**: P1 - High  
**Goal**: Make releases available on PRs/pushes but require validation and be manually triggered, with different behavior on dev vs main

#### Activity 7.1: Update publish-pypi-dev.yml to be available but require validation
**File**: `.github/workflows/publish-pypi-dev.yml`

**Task 7.1.1**: Add PR and push triggers (makes workflow available), but require validation
- **Line 3-9**: Change to:
  ```yaml
  on:
    pull_request:
      branches: [dev]  # Available on PRs but not automatic
    push:
      branches: [dev]  # Available on pushes but not automatic
    workflow_dispatch:  # Manual trigger
    workflow_run:  # Trigger after validation workflows pass
      workflows: ["CI/CD Pipeline", "Test", "Version Check"]
      types:
        - completed
      branches: [dev]
  ```

**Task 7.1.2**: Add validation check job
- **After line 14**, add new job:
  ```yaml
  jobs:
    check-validation:
      name: check-validation
      runs-on: ubuntu-latest
      if: |
        github.event_name == 'workflow_dispatch' ||
        (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success')
      steps:
        - name: Check if validation workflows passed
          uses: actions/github-script@v7
          with:
            script: |
              // For PRs, check if required workflows have passed
              if (context.eventName === 'pull_request') {
                const { data: checks } = await github.rest.checks.listForRef({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  ref: context.payload.pull_request.head.sha,
                });
                const requiredChecks = ['CI/CD Pipeline', 'Test', 'Version Check'];
                const passedChecks = checks.check_runs.filter(
                  check => requiredChecks.includes(check.name) && check.conclusion === 'success'
                );
                if (passedChecks.length < requiredChecks.length) {
                  core.setFailed('Required validation workflows must pass first');
                }
              }
    
    publish-nightly:
      name: publish-dev-to-pypi
      needs: check-validation
      if: |
        github.event_name == 'workflow_dispatch' ||
        (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') ||
        (github.event_name == 'pull_request' && needs.check-validation.result == 'success') ||
        (github.event_name == 'push' && needs.check-validation.result == 'success')
      # ... existing steps
  ```

**Task 7.1.3**: Use existing version validation script
- **Line 42-54**: Replace with call to `validate_version.py`:
  ```yaml
  - name: Validate version using script
    run: |
      uv run python dev/scripts/validate_version.py || exit 1
  ```

#### Activity 6.2: Update release.yml for manual releases with version bumping
**File**: `.github/workflows/release.yml`

**Task 6.2.1**: Keep manual only, add automatic version bumping for main
- **Line 3-7**: Keep as-is (workflow_dispatch and tag push):
  ```yaml
  on:
    push:
      tags:
        - 'v*'
    workflow_dispatch:
      inputs:
        version:
          description: 'Version to release (e.g., 0.1.0)'
          required: true
          type: string
  ```

**Task 7.2.3**: Add version bumping step for main branch (when triggered manually or on push)
- **After line 31** (after checkout), add version bumping logic if on main and no version input:
  ```yaml
  - name: Bump version for main (if needed)
    if: |
      github.ref == 'refs/heads/main' &&
      (github.event_name == 'workflow_dispatch' || github.event_name == 'push') &&
      (github.event.inputs.version == '' || github.event.inputs.version == null)
    run: |
      # Extract current version
      CURRENT=$(grep -E '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
      MAJOR=$(echo "$CURRENT" | cut -d. -f1)
      MINOR=$(echo "$CURRENT" | cut -d. -f2)
      
      # Calculate new version: {major}.{minor+1}.0 (reset patch to 0)
      NEW_MINOR=$((MINOR + 1))
      NEW_VERSION="$MAJOR.$NEW_MINOR.0"
      
      # Update version in both files
      sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
      sed -i "s/^__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" ccbt/__init__.py
      
      # Validate using script
      uv run python dev/scripts/validate_version.py || exit 1
      
      echo "version=$NEW_VERSION" >> $GITHUB_OUTPUT
      echo "✅ Bumped version from $CURRENT to $NEW_VERSION"
  ```

**Task 7.2.4**: Use validate_version.py for validation
- **Line 27-48**: Replace inline validation with script call:
  ```yaml
  - name: Validate version using script
    run: |
      uv run python dev/scripts/validate_version.py || exit 1
  ```

---

## Priority 2: Documentation and Reports

### PROJECT 8: Fix Documentation Reports (Manual Only)
**Priority**: P2 - Medium  
**Goal**: Make report generation always manual, never automatic

#### Activity 7.1: Create reports generation workflow (manual only)
**File**: `.github/workflows/generate-reports.yml` (NEW FILE)

**Task 7.1.1**: Create workflow for report generation (manual trigger only)
- **Lines 1-20**: Setup and trigger (manual only):
  ```yaml
  name: Generate Reports
  
  on:
    workflow_dispatch:  # Manual only, never automatic
  
  concurrency:
    group: generate-reports-${{ github.ref }}
    cancel-in-progress: false
  
  jobs:
    generate-coverage:
      name: generate-coverage
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - name: Install UV
          uses: astral-sh/setup-uv@v4
        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.11'
        - name: Install dependencies
          run: uv sync --dev
        - name: Run tests with coverage
          run: |
            uv run pytest -c dev/pytest.ini tests/ \
              --cov=ccbt \
              --cov-report=html:site/reports/htmlcov \
              --cov-report=xml:coverage.xml
        - name: Upload coverage report
          uses: actions/upload-artifact@v4
          with:
            name: coverage-report
            path: |
              site/reports/htmlcov/
              coverage.xml
  
    generate-bandit:
      name: generate-bandit
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - name: Install UV
          uses: astral-sh/setup-uv@v4
        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.11'
        - name: Install dependencies
          run: uv sync --dev
        - name: Ensure bandit directory
          run: uv run python tests/scripts/ensure_bandit_dir.py
        - name: Run Bandit scan
          run: |
            uv run bandit -r ccbt/ -f json -o docs/reports/bandit/bandit-report.json \
              --severity-level medium \
              -x tests,benchmarks,dev,dist,docs,htmlcov,site,.venv,.pre-commit-cache,.pre-commit-home,.pytest_cache,.ruff_cache,.hypothesis,.github,.ccbt,.cursor,.benchmarks
        - name: Upload bandit report
          uses: actions/upload-artifact@v4
          with:
            name: bandit-report
            path: docs/reports/bandit/bandit-report.json
  
    generate-benchmarks:
      name: generate-benchmarks
      runs-on: ubuntu-latest
      permissions:
        contents: write
      steps:
        - uses: actions/checkout@v4
          with:
            fetch-depth: 0
        - name: Install UV
          uses: astral-sh/setup-uv@v4
        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.11'
        - name: Install dependencies
          run: uv sync --dev
        - name: Run benchmarks
          run: |
            uv run python tests/performance/bench_hash_verify.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
            uv run python tests/performance/bench_disk_io.py --quick --sizes 256KiB 1MiB --record-mode=commit --config-file docs/examples/example-config-performance.toml
            uv run python tests/performance/bench_piece_assembly.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
            uv run python tests/performance/bench_loopback_throughput.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
            uv run python tests/performance/bench_encryption.py --quick --record-mode=commit --config-file docs/examples/example-config-performance.toml
        - name: Commit benchmark results
          if: github.ref == 'refs/heads/main' && github.event_name == 'push'
          run: |
            git config --local user.email "action@github.com"
            git config --local user.name "GitHub Action"
            git add -f docs/reports/benchmarks/
            git diff --staged --quiet || (git commit -m "ci: record benchmark results [skip ci]" && git push)
  
    commit-reports:
      name: commit-reports
      needs: [generate-coverage, generate-bandit, generate-benchmarks]
      runs-on: ubuntu-latest
      permissions:
        contents: write
      steps:
        - uses: actions/checkout@v4
        - name: Download coverage report
          uses: actions/download-artifact@v4
          with:
            name: coverage-report
            path: site/reports/htmlcov/
        - name: Download bandit report
          uses: actions/download-artifact@v4
          with:
            name: bandit-report
            path: docs/reports/bandit/
        - name: Copy bandit report to docs location
          run: |
            mkdir -p docs/en/reports/bandit
            cp docs/reports/bandit/bandit-report.json docs/en/reports/bandit/bandit-report.json || true
        - name: Commit reports
          if: github.ref == 'refs/heads/main' && github.event_name == 'push'
          run: |
            git config --local user.email "action@github.com"
            git config --local user.name "GitHub Action"
            git add site/reports/htmlcov/ docs/reports/bandit/ docs/en/reports/bandit/
            git diff --staged --quiet || (git commit -m "ci: update reports for documentation [skip ci]" && git push)
  ```

#### Activity 7.2: Update build-documentation.yml to require validation
**File**: `.github/workflows/build-documentation.yml`

**Task 7.2.1**: Add PR trigger and workflow_run to make it available on PRs
- **Line 3-19**: Update to:
  ```yaml
  on:
    push:
      branches: [main]
      paths:
        - 'docs/**'
        - 'dev/mkdocs.yml'
        - '.readthedocs.yaml'
        - 'dev/requirements-rtd.txt'
        - 'ccbt/**'
    pull_request:
      branches: [dev, main]  # Available on PRs but not automatic
      paths:
        - 'docs/**'
        - 'dev/mkdocs.yml'
        - '.readthedocs.yaml'
        - 'dev/requirements-rtd.txt'
        - 'ccbt/**'
    workflow_dispatch:
    workflow_run:  # Trigger after validation workflows pass
      workflows: ["CI/CD Pipeline", "Test"]
      types:
        - completed
      branches: [dev, main]
  ```

**Task 7.2.2**: Add validation check job
- **After line 23**, add new job:
  ```yaml
  jobs:
    check-validation:
      name: check-validation
      runs-on: ubuntu-latest
      if: |
        github.event_name == 'workflow_dispatch' ||
        (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success')
      steps:
        - name: Check if validation workflows passed
          uses: actions/github-script@v7
          with:
            script: |
              // For PRs, check if ci.yml and test.yml have passed
              if (context.eventName === 'pull_request') {
                const { data: checks } = await github.rest.checks.listForRef({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  ref: context.payload.pull_request.head.sha,
                });
                const requiredChecks = ['CI/CD Pipeline', 'Test'];
                const passedChecks = checks.check_runs.filter(
                  check => requiredChecks.includes(check.name) && check.conclusion === 'success'
                );
                if (passedChecks.length < requiredChecks.length) {
                  core.setFailed('Required validation workflows must pass first');
                }
              }
    
    build-docs:
      name: build-docs
      needs: check-validation
      if: |
        github.event_name == 'workflow_dispatch' ||
        (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') ||
        (github.event_name == 'pull_request' && needs.check-validation.result == 'success') ||
        (github.event_name == 'push' && github.ref == 'refs/heads/main')
      # ... existing steps
  ```

**Task 7.2.3**: Keep inline report generation
- **Lines 110-119**: Keep coverage generation (works fine)
- **Lines 115-119**: Keep bandit generation (works fine)

#### Activity 7.3: Update benchmark.yml to be manual only
**File**: `.github/workflows/benchmark.yml`

**Task 7.3.1**: Remove push trigger, keep manual only
- **Line 3-9**: Change to:
  ```yaml
  on:
    workflow_dispatch:  # Manual only, never automatic
  ```

**Task 7.3.2**: Keep existing benchmark logic
- **Lines 40-77**: Keep as-is (works fine)

---

### PROJECT 9: Update .gitignore
**Priority**: P2 - Medium  
**Goal**: Remove local benchmark reports from git tracking

#### Activity 8.1: Update .gitignore
**File**: `.gitignore`

**Task 8.1.1**: Add explicit ignore for local benchmark reports
- **Line 334**: Update comment to clarify CI/CD will force-add
- **Add after line 337**: `docs/reports/benchmarks/runs/*.json`

---

## Workflow Execution Order

### On Pull Request to Dev Branch

**All verifications run on PRs to dev (not on push):**

1. **`ci.yml`** - Lint and type check (automatic)
2. **`test.yml`** - Run full test suite (automatic)
3. **`version-check.yml`** - Version validation (automatic, using `validate_version.py`)

**Expensive operations available but require validation and manual trigger:**
4. **`compatibility.yml`** - Available on PR but requires validation, manual trigger only
5. **`build-documentation.yml`** - Available on PR but requires validation, manual trigger only
6. **`publish-pypi-dev.yml`** - Available on PR but requires validation, manual trigger only

**No automatic expensive actions on PRs - all require validation and manual trigger**

---

### On Push to Dev Branch

**No verifications run** (already validated on PR)

**Expensive operations available but require validation and manual trigger:**
1. **`publish-pypi-dev.yml`** - Available on push but requires validation, manual trigger only
   - Uses existing version from `pyproject.toml`
   - No version bumping
   - Just publishes current version
   - Requires CI/CD Pipeline, Test, and Version Check to pass first

2. **`compatibility.yml`** - Available on push but requires validation, manual trigger only
   - Very expensive and time-consuming
   - Requires CI/CD Pipeline and Test to pass first

3. **`build-documentation.yml`** - Available on push but requires validation, manual trigger only
   - Requires CI/CD Pipeline and Test to pass first

---

### On Push to Main Branch

**No verifications run** (already validated on PRs to dev)

**Automatic Actions:**
1. **`build.yml`** - Automatic build
   - Builds packages and Windows executable
   - No validation needed (already done on PR)

2. **`build-documentation.yml`** - Automatic documentation build (on push to main)
   - Works fine as-is
   - Generates reports inline if needed
   - Builds documentation

**Expensive operations available but require validation and manual trigger:**
1. **`compatibility.yml`** - Available on push but requires validation, manual trigger only
2. **`release.yml`** - Available on push but requires validation, manual trigger only
   - Different version bump logic than dev
   - Uses automatic version bumping (increments minor, resets patch)
   - Uses `validate_version.py` for validation
   - Creates release and publishes to PyPI

**Manual Actions:**
1. **`generate-reports.yml`** - Manual only (never automatic)
   - Must be triggered manually
   - Generates coverage, bandit, benchmarks
   - Commits reports if needed

---

### Version Bumping Logic

**On Dev Branch (Manual Release):**
- Uses existing version from `pyproject.toml`
- No automatic bumping
- Validates using `validate_version.py`
- Must be > 0.0.0

**On Main Branch (Manual Release):**
- Automatic version bump: `{major}.{minor+1}.0` (increments minor, resets patch)
- Uses existing logic from `release-to-main.yml`
- Validates using `validate_version.py`
- Must be >= 0.1.0
- Updates both `pyproject.toml` and `ccbt/__init__.py`

---

## Pattern: "Available but Require Validation"

For expensive operations (compatibility tests, documentation builds, releases), the plan uses a pattern where workflows are **available on PRs/pushes** but **require validation and manual trigger**:

### How It Works

1. **Workflow appears in PR/push checks** - Using `pull_request` and `push` triggers makes the workflow visible in GitHub's PR/push checks UI
2. **Validation check job** - First job checks if required validation workflows (ci.yml, test.yml) have passed
3. **Manual trigger required** - Workflow doesn't run automatically, but can be triggered:
   - Via `workflow_dispatch` (manual trigger, bypasses validation check)
   - Via `workflow_run` (after validation workflows complete successfully)
   - From PR/push context (if validation check passes)

### Implementation Pattern

```yaml
on:
  pull_request:
    branches: [dev, main]  # Makes workflow available on PRs
  push:
    branches: [dev, main]  # Makes workflow available on pushes
  workflow_dispatch:  # Manual trigger
  workflow_run:  # Trigger after validation workflows pass
    workflows: ["CI/CD Pipeline", "Test"]
    types:
      - completed
    branches: [dev, main]

jobs:
  check-validation:
    name: check-validation
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success')
    steps:
      - name: Check if validation workflows passed
        uses: actions/github-script@v7
        with:
          script: |
            // For PRs, check if required workflows have passed
            if (context.eventName === 'pull_request') {
              const { data: checks } = await github.rest.checks.listForRef({
                owner: context.repo.owner,
                repo: context.repo.repo,
                ref: context.payload.pull_request.head.sha,
              });
              const requiredChecks = ['CI/CD Pipeline', 'Test'];
              const passedChecks = checks.check_runs.filter(
                check => requiredChecks.includes(check.name) && check.conclusion === 'success'
              );
              if (passedChecks.length < requiredChecks.length) {
                core.setFailed('Required validation workflows must pass first');
              }
            }
  
  expensive-operation:
    name: expensive-operation
    needs: check-validation
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success') ||
      (github.event_name == 'pull_request' && needs.check-validation.result == 'success') ||
      (github.event_name == 'push' && needs.check-validation.result == 'success')
    # ... actual expensive operation
```

### Benefits

- ✅ Workflows appear in PR/push checks (visible to developers)
- ✅ Validation required before expensive operations run
- ✅ Can be triggered manually when needed
- ✅ Can be triggered automatically after validation passes (via workflow_run)
- ✅ Prevents expensive operations from running unnecessarily

---

## Concurrency Groups Summary

| Workflow | Concurrency Group | Purpose |
|----------|------------------|---------|
| `benchmark.yml` | `benchmark-write-${{ github.ref }}` | Prevent parallel benchmark commits |
| `release-to-main.yml` | `release-to-main` | Prevent parallel releases |
| `build-documentation.yml` | `docs-build-${{ github.ref }}` | Prevent parallel doc builds |
| `generate-reports.yml` | `generate-reports-${{ github.ref }}` | Prevent parallel report generation |
| `publish-pypi-dev.yml` | `dev-nightly-release` | Prevent parallel dev publishes |
| `release.yml` | `main-release` | Prevent parallel main releases |
| `compatibility.yml` | `compatibility-${{ github.ref }}` | Prevent parallel compatibility tests |
| `build.yml` | `build-${{ github.ref }}` | Prevent parallel builds |

---

## Implementation Order

1. **Phase 1 (Critical - Blocks All Operations)**:
   - PROJECT 1: Add Concurrency Controls
   - PROJECT 2: Fix Compatibility Tests
   - PROJECT 3: Fix Version Check Workflow
   - PROJECT 4: Fix release-to-main.yml

2. **Phase 2 (High Priority - Build Automation)**:
   - PROJECT 5: Fix Build Workflows
   - PROJECT 6: Fix Windows .exe Build
   - PROJECT 7: Fix Release Workflows

3. **Phase 3 (Medium Priority - Documentation)**:
   - PROJECT 8: Fix Documentation Reports
   - PROJECT 9: Update .gitignore

---

## Testing Strategy

1. **Test Concurrency Controls**:
   - Trigger multiple workflows simultaneously → should queue, not conflict
   - Verify only one write operation happens at a time

2. **Test Compatibility Tests**:
   - Create PR to dev → workflow should be available but not run automatically
   - Push to dev → workflow should be available but not run automatically
   - Manual dispatch → should work (bypasses validation check)
   - After validation passes → can be triggered via workflow_run
   - Verify validation check job requires ci.yml and test.yml to pass first

3. **Test Version Check**:
   - Create PR to dev → should run version validation
   - Push to dev → should NOT run version validation
   - Push to main → should NOT run version validation
   - Manual dispatch → should work

4. **Test release-to-main**:
   - Run workflow manually → should merge dev into main, then bump version
   - Verify merge commit exists
   - Verify version bump happens after merge (increments minor, resets patch)
   - Verify version validation script is called

5. **Test Builds**:
   - Push to main → should build automatically
   - Push to dev → should NOT build
   - PR to main → should NOT build
   - Manual dispatch → should build
   - Verify Windows .exe builds after package build

6. **Test Releases**:
   - Push to dev → workflow should be available but not run automatically
   - Push to main → workflow should be available but not run automatically
   - Create PR to dev/main → workflow should be available but not run automatically
   - Manual release on dev → should require validation, then publish to PyPI with existing version
   - Manual release on main → should require validation, then bump version automatically, then publish
   - After validation passes → can be triggered via workflow_run
   - Verify version bumping uses existing logic

7. **Test Documentation**:
   - Push to main → should build docs automatically (works fine as-is)
   - Create PR to dev/main → workflow should be available but not run automatically
   - Manual dispatch → should build docs (bypasses validation check)
   - After validation passes → can be triggered via workflow_run
   - Reports generation → manual only, never automatic

---

## Success Criteria

- ✅ Compatibility tests available on PRs/pushes but require validation and manual trigger (very expensive and time-consuming)
- ✅ Documentation builds available on PRs/pushes but require validation and manual trigger (except automatic on push to main)
- ✅ Releases available on PRs/pushes but require validation and manual trigger
- ✅ Version validation only runs on PRs to dev (not on push)
- ✅ Version bumping uses existing scripts and logic
- ✅ release-to-main actually merges code before bumping version
- ✅ Builds only happen on push to main or manual (not on PRs)
- ✅ Windows .exe builds successfully after package build
- ✅ Dev branch: nightly PyPI publishes available on PRs/pushes but require validation and manual trigger
- ✅ Main branch: releases available on PRs/pushes but require validation and manual trigger (with automatic version bumping)
- ✅ Reports generation always manual (never automatic)
- ✅ No race conditions on write operations (concurrency controls)
- ✅ No verifications on push (only on PRs to dev)
- ✅ Local benchmark reports are ignored, CI/CD reports are tracked

---

## Notes

- All workflows use explicit permissions
- All workflows have proper error handling
- All workflows have `workflow_dispatch` for manual testing
- Use `workflow_call` for better orchestration
- Ensure proper artifact sharing between workflows
- Add proper logging and debugging output
- Use `concurrency:` groups to prevent race conditions
- Use `needs:` to ensure proper sequencing
- Use `if:` conditions to control execution flow
- All write operations are protected by concurrency groups
