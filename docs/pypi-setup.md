# PyPI Publishing Setup

This document describes how to configure and use the PyPI publishing workflow for ccBitTorrent.

## Overview

The project uses `uv` as the package manager for building and publishing to PyPI. The publishing workflow is automated via GitHub Actions and triggers on version tags.

## Workflow Files

- **`.github/workflows/publish-pypi.yml`**: Dedicated workflow for PyPI publishing using `uv`
- **`.github/workflows/release.yml`**: Release workflow that builds packages using `uv build`

## Prerequisites

1. **PyPI Account**: You need a PyPI account with API token access
2. **GitHub Secrets**: The PyPI API token must be stored as a GitHub secret

## Setting Up PyPI API Token

### Step 1: Create PyPI API Token

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/)
2. Navigate to **API tokens** section
3. Click **Add API token**
4. Provide a token name (e.g., "ccBitTorrent CI/CD")
5. Set the scope:
   - **Entire account**: For publishing all projects
   - **Project: ccbt**: For publishing only the ccbt project (recommended)
6. Click **Add token**
7. **Copy the token immediately** - it will only be shown once!

The token format is: `pypi-...`

### Step 2: Add Token to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Set:
   - **Name**: `PYPI_API_TOKEN`
   - **Secret**: Paste your PyPI API token (the full token starting with `pypi-`)
5. Click **Add secret**

## Workflow Configuration

### Publishing Workflow (`.github/workflows/publish-pypi.yml`)

The workflow automatically:

1. **Triggers**:
   - On push of tags matching `v*` (e.g., `v0.1.0`)
   - Manual dispatch via GitHub Actions UI

2. **Build Process**:
   - Installs `uv` using `astral-sh/setup-uv@v4`
   - Sets up Python 3.11
   - Installs project dependencies with `uv sync --dev`
   - Builds package with `uv build` (replaces `python -m build`)
   - Verifies package with `twine check` (if available)

3. **Publishing**:
   - Uses `uv publish` with token from `UV_PYPI_TOKEN` environment variable
   - Automatically authenticates using the GitHub secret

4. **Verification**:
   - Waits for PyPI propagation
   - Verifies package availability

### Manual Publishing

You can also publish manually using `uv`:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Build the package
uv build

# Publish to PyPI
export UV_PYPI_TOKEN="pypi-your-token-here"
uv publish
```

Or using explicit credentials:

```bash
uv publish --username __token__ --password "pypi-your-token-here"
```

## Version Management

### Tag-Based Releases

The workflow extracts the version from Git tags:

- Tag format: `v0.1.0`, `v1.2.3`, etc.
- Version is extracted by removing the `v` prefix
- The version in `pyproject.toml` should match the tag

### Updating Version

Before creating a release tag:

1. Update version in `pyproject.toml`:
   ```toml
   [project]
   version = "0.1.0"
   ```

2. Commit the change:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.1.0"
   ```

3. Create and push the tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. The workflow will automatically:
   - Build the package
   - Publish to PyPI
   - Create a GitHub release (via `release.yml`)

## Package Installation

After publishing, users can install the package:

```bash
# Using uv (recommended)
uv pip install ccbt

# Using pip
pip install ccbt

# Specific version
uv pip install ccbt==0.1.0
```

## Troubleshooting

### Workflow Fails with "PYPI_API_TOKEN secret is not set"

**Solution**: Add the PyPI API token as a GitHub secret named `PYPI_API_TOKEN`.

### Package Already Exists Error

**Cause**: The version already exists on PyPI.

**Solution**: 
- Bump the version in `pyproject.toml`
- Create a new tag with the updated version
- PyPI does not allow overwriting existing versions

### Authentication Failed

**Possible causes**:
- Token is invalid or expired
- Token doesn't have permission for the project
- Token format is incorrect

**Solution**:
- Verify the token in PyPI account settings
- Ensure the token scope includes the `ccbt` project
- Recreate the token if necessary
- Update the GitHub secret with the new token

### Build Fails

**Common issues**:
- Missing dependencies in `pyproject.toml`
- Invalid package metadata
- Build backend issues

**Solution**:
- Check `pyproject.toml` for correct metadata
- Test build locally: `uv build`
- Verify package structure: `uv run twine check dist/*`

## Security Best Practices

1. **Never commit tokens**: The PyPI token should only exist in GitHub Secrets
2. **Use project-scoped tokens**: Limit token scope to the specific project
3. **Rotate tokens regularly**: Regenerate tokens periodically
4. **Monitor token usage**: Check PyPI account for unexpected activity
5. **Use least privilege**: Grant only necessary permissions

## Integration with Release Workflow

The `release.yml` workflow handles:
- Pre-release checks (linting, testing, security scans)
- Package building (using `uv build`)
- GitHub release creation
- Post-release verification

The `publish-pypi.yml` workflow handles:
- PyPI publication
- PyPI verification

Both workflows can run in parallel or sequentially, depending on your needs.

## References

- [uv Documentation - Publishing](https://docs.astral.sh/uv/publishing/)
- [uv Documentation - Building](https://docs.astral.sh/uv/packaging/building/)
- [PyPI API Tokens Documentation](https://pypi.org/help/#apitoken)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

