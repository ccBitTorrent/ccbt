# Read the Docs Configuration

This document describes the Read the Docs (RTD) configuration for ccBitTorrent documentation.

## Configuration Files

### `.readthedocs.yaml` (Root Directory)

**Location**: Repository root (required by Read the Docs)

This file configures how Read the Docs builds the documentation:

- **Build Environment**: Ubuntu 24.04 with Python 3.11
- **MkDocs Configuration**: Points to `dev/mkdocs.yml`
- **Dependencies**: Installs from `dev/requirements-rtd.txt` and the project itself
- **Output Formats**: HTML (default), HTMLZIP, and PDF

**Note**: Read the Docs requires this file to be in the root directory. It cannot be placed in a subdirectory like `dev/`.

### `dev/requirements-rtd.txt`

**Location**: `dev/` directory

This file contains all MkDocs-related dependencies needed for building documentation:

- MkDocs core and Material theme
- MkDocs plugins (git-revision-date, mkdocstrings, codeinclude, coverage)
- Markdown extensions (pymdown-extensions)
- Critical runtime dependencies (pydantic, pyyaml)

The project itself is installed separately via `pip install -e .` to ensure all runtime dependencies are available for `mkdocstrings` to parse the code.

### `dev/mkdocs.yml`

**Location**: `dev/` directory

The main MkDocs configuration file that defines:
- Site structure and navigation
- Theme settings
- Plugin configurations
- Markdown extensions

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/docs.yml` workflow:

1. **Triggers**: 
   - Pushes to `main` and `dev` branches
   - Changes to `docs/`, `dev/mkdocs.yml`, `.readthedocs.yaml`, `dev/requirements-rtd.txt`, or `ccbt/`

2. **Build Process**:
   - Installs dependencies using `uv`
   - Generates coverage and Bandit reports (optional, non-blocking)
   - Builds documentation using MkDocs
   - Uploads artifacts
   - Deploys to GitHub Pages (main branch only)

### Read the Docs Webhook

To enable automatic builds on Read the Docs when changes are pushed:

1. **In Read the Docs**:
   - Go to your project's **Admin** → **Integrations**
   - Copy the webhook URL and secret

2. **In GitHub**:
   - Go to **Settings** → **Webhooks** → **Add webhook**
   - **Payload URL**: Use the RTD webhook URL
   - **Content type**: `application/json`
   - **Secret**: Use the RTD webhook secret
   - **Events**: Select "Just the push event" or "Let me select individual events" and choose:
     - Branch or tag creation
     - Branch or tag deletion
     - Pushes
   - **Active**: ✓

3. **In Read the Docs**:
   - Go to **Admin** → **Versions**
   - Ensure the `dev` branch is active
   - Set `dev` as the default version if desired

## Branch Configuration

The Read the Docs project should be configured to:

- **Track Branch**: `dev` (or `main` as primary)
- **Default Version**: Set according to your preference
- **Active Versions**: Ensure `dev` and `main` are both active

## Build Process

When Read the Docs builds your documentation:

1. Checks out the repository (from the configured branch)
2. Reads `.readthedocs.yaml` from the root
3. Sets up Python 3.11 environment on Ubuntu 24.04
4. Installs dependencies from `dev/requirements-rtd.txt`
5. Installs the project itself (`pip install -e .`)
6. Runs `mkdocs build` using `dev/mkdocs.yml`
7. Publishes the built documentation

## Troubleshooting

### Build Failures

1. **Check Build Logs**: 
   - Go to your RTD project → **Builds**
   - Click on the failed build to see detailed logs

2. **Common Issues**:
   - **Missing dependencies**: Ensure `dev/requirements-rtd.txt` includes all needed packages
   - **Import errors**: The project must be installed for `mkdocstrings` to work
   - **Path issues**: Ensure `dev/mkdocs.yml` paths are correct relative to the repository root
   - **System dependencies**: Some dependencies like `liburing` may require system packages (usually handled by conditional dependencies)

3. **Verify Configuration**:
   - Ensure `.readthedocs.yaml` is in the root directory
   - Verify `dev/mkdocs.yml` exists and is valid
   - Check that `dev/requirements-rtd.txt` includes all MkDocs dependencies

### Testing Locally

To test the Read the Docs build locally:

```bash
# Install dependencies
pip install -r dev/requirements-rtd.txt
pip install -e .

# Build documentation
mkdocs build --strict -f dev/mkdocs.yml
```

## File Structure

```
.
├── .readthedocs.yaml          # RTD configuration (must be in root)
├── dev/
│   ├── mkdocs.yml             # MkDocs configuration
│   └── requirements-rtd.txt   # RTD build dependencies
├── docs/                      # Documentation source files
└── .github/
    └── workflows/
        └── docs.yml           # CI/CD workflow
```

## References

- [Read the Docs Configuration File Documentation](https://docs.readthedocs.io/en/stable/config-file/v2.html)
- [MkDocs User Guide](https://www.mkdocs.org/user-guide/)
- [Read the Docs Continuous Deployment](https://docs.readthedocs.io/en/stable/continuous-deployment.html)


