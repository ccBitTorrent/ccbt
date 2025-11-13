# Release Checklist

Use this checklist when preparing a new release of ccBitTorrent.

## Pre-Release

### Version Management
- [ ] Update version in `pyproject.toml`
- [ ] Update version in `ccbt/__init__.py` (if applicable)
- [ ] Update CHANGELOG.md with release notes
- [ ] Verify all version references are consistent

### Code Quality
- [ ] All tests pass: `uv run pytest -c dev/pytest.ini tests/ -v`
- [ ] Coverage meets threshold (99%): `uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=term-missing`
- [ ] Linting passes: `uv run ruff --config dev/ruff.toml check ccbt/`
- [ ] Type checking passes: `uv run ty check --config-file=dev/ty.toml --output-format=concise`
- [ ] Security scan passes: `uv run bandit -r ccbt/`
- [ ] Pre-commit hooks pass: `uv run pre-commit run --all-files -c dev/pre-commit-config.yaml`

### Documentation
- [ ] Documentation builds successfully: `uv run mkdocs build --strict -f dev/mkdocs.yml`
- [ ] All API documentation is up to date
- [ ] `.github/README.md` is updated if needed
- [ ] `docs/README_PyPI.md` is updated if needed
- [ ] Examples are tested and working

### Testing
- [ ] Unit tests pass on all supported Python versions (3.8-3.12)
- [ ] Integration tests pass
- [ ] Compatibility tests pass
- [ ] Benchmarks are recorded and within acceptable ranges
- [ ] Manual testing of key features completed

### Build Verification
- [ ] Package builds successfully: `uv run python -m build`
- [ ] Package validation passes: `uv run twine check dist/*`
- [ ] Windows executable builds successfully (if applicable)
- [ ] Test installation from wheel: `uv pip install dist/*.whl`

## Release Process

### Git Operations
- [ ] Create release branch: `git checkout -b release/vX.Y.Z`
- [ ] Commit version updates and changelog
- [ ] Push release branch: `git push origin release/vX.Y.Z`
- [ ] Create pull request to `main`
- [ ] Get code review approval
- [ ] Merge to `main`

### Tagging
- [ ] Create annotated tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Push tag: `git push origin vX.Y.Z`

### GitHub Release
- [ ] Create GitHub Release from tag
- [ ] Use release notes from CHANGELOG.md
- [ ] Attach Windows executables (if applicable)
- [ ] Mark as latest release (if applicable)

### Deployment
- [ ] Verify PyPI package is published automatically
- [ ] Verify GitHub Release is created with assets
- [ ] Verify documentation is deployed to GitHub Pages
- [ ] Test installation from PyPI: `uv pip install ccbt`

## Post-Release

### Verification
- [ ] Verify PyPI package is accessible: https://pypi.org/project/ccbt/
- [ ] Verify GitHub Release is published: https://github.com/ccBittorrent/ccbt/releases
- [ ] Verify documentation is live: https://ccbittorrent.readthedocs.io/
- [ ] Test fresh installation in clean environment

### Communication
- [ ] Update project status (if applicable)
- [ ] Announce release in discussions (if applicable)
- [ ] Update any external documentation or references

### Follow-up
- [ ] Monitor for issues after release
- [ ] Address any critical bugs discovered
- [ ] Plan next release cycle

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

Example: `v1.2.3` = Major 1, Minor 2, Patch 3

## Emergency Hotfix Process

For critical bugs in production:

1. Create hotfix branch from `main`: `git checkout -b hotfix/vX.Y.Z`
2. Fix the issue
3. Update version (patch increment)
4. Update CHANGELOG.md
5. Create PR to `main`
6. After merge, tag and release immediately
7. Merge back to `dev` branch

---

**Last Updated**: 2025-01-XX

