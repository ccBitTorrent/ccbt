# Release Checklist

This checklist ensures every ccBitTorrent release is consistent, well-tested, and synchronized across code, documentation, and translations. Work through each section in order and keep links updated if files move.

!!! note
    Reference supporting docs as you go:
    - [CI/CD guide](CI_CD.md)
    - [Configuration guide](configuration.md)
    - [API reference](API.md)
    - [Documentation standards](i18n/translation-guide.md)

## 1. Pre-release Preparation

- [ ] **Stabilize scope**
  - [ ] Confirm target issues/MRs are merged and labeled with the release milestone.
  - [ ] Review blockers and ensure regressions from the previous release are closed.
- [ ] **Versioning + changelog**
  - [ ] Bump version strings in `pyproject.toml`, `ccbt/__init__.py`, and `docs/en/index.md`.
  - [ ] Append a release section to `CHANGELOG.md` (date, highlights, contributor credits).
  - [ ] Update sample config files under `docs/en/examples/`.
- [ ] **Quality gates**
  - [ ] Run `uv run pre-commit run --all-files -c dev/pre-commit-config.yaml`.
  - [ ] Run `uv run pytest -c dev/pytest.ini tests/ -v --tb=short --maxfail=1`.
  - [ ] Run `uv run ty check --config-file=dev/ty.toml --output-format=concise`.
  - [ ] Run security scans (`uv run bandit …`, `uv run safety scan`).
- [ ] **Documentation sync**
  - [ ] Verify `docs/en/API.md` documents all exported modules and latest public classes.
  - [ ] Verify `docs/en/configuration.md` matches `ccbt/models.py` and `ccbt.toml`.
  - [ ] Rebuild docs locally: `uv run mkdocs build --strict -f dev/mkdocs.yml`.
  - [ ] Ensure `docs/en/unimplemented-methods.md` and this checklist are up to date.
- [ ] **Translation + localization**
  - [ ] Run `python -m ccbt.i18n.scripts.extract` then `msgmerge` for every locale.
  - [ ] Use `python -m ccbt.i18n.scripts.check_completeness` → target ≥95% coverage for `yo`, `sw`, `arc`.
  - [ ] Compile locales: `python -m ccbt.i18n.scripts.compile_all`.
  - [ ] Smoke test `CCBT_LOCALE=yo|sw|arc btbt status`.

## 2. Release Execution

- [ ] **Build artifacts**
  - [ ] Run `uv build` (wheel + sdist) and verify outputs under `dist/`.
  - [ ] Validate distribution: `uv run twine check dist/*`.
- [ ] **Artifact verification**
  - [ ] Install wheel from `dist/` into a clean venv and run `btbt --help`.
  - [ ] Run targeted smoke tests (CLI download, daemon start/stop, Bitonic launch).
- [ ] **Tag + publish**
  - [ ] Create annotated tag `vX.Y.Z` with changelog summary.
  - [ ] Push tag to origin; monitor GitHub Actions release workflow.
  - [ ] Upload wheel/sdist to PyPI (`uv publish` or `twine upload dist/*`).
  - [ ] Publish GitHub release notes (include checksums, highlights, upgrade notes).
- [ ] **Docs + site**
  - [ ] Trigger Read the Docs build (or wait for webhook) and verify latest docs.
  - [ ] Deploy site artifacts from `site/` if GitHub Pages hosting is used.
  - [ ] Update coverage and Bandit reports under `docs/en/reports/`.

## 3. Post-release Follow-up

- [ ] **Communication**
  - [ ] Publish blog post in `docs/blog/` summarizing the release.
  - [ ] Share announcement on Discord, X/Twitter, and mailing list (if applicable).
- [ ] **Backlog + tracking**
  - [ ] Create tracking issue for next release (collect regressions + follow-ups).
  - [ ] Move unfinished tasks to the next milestone or close as deferred.
- [ ] **Evidence + archiving**
  - [ ] Store CI artifacts and coverage reports for audit (link in release notes).
  - [ ] Update `docs/en/RELEASE_CHECKLIST.md` with any process changes noticed.
- [ ] **Localization maintenance**
  - [ ] Capture outstanding translation gaps in `docs/i18n-translation-status.md`.
  - [ ] Notify translators with the latest glossary deltas for `yo`, `sw`, `arc`.

Keep this checklist versioned with the codebase. When the release process evolves (new workflows, tooling, or compliance steps), update this file before cutting the next release tag.

