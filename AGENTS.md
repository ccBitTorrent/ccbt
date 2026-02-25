# AGENTS.md

## Cursor Cloud specific instructions

### Overview

ccBitTorrent (`ccbt`) is a standalone Python BitTorrent client with three CLI entry points: `ccbt`, `btbt`, and `bitonic`. It has no external service dependencies (no databases, caches, or message queues). All commands are documented in `.cursor/rules/development-patterns.mdc` and `docs/en/contributing.md`.

### Environment prerequisites

- **Python 3.12** with `python3-dev` and `build-essential` (needed for C extensions like `netifaces` and `liburing`)
- **uv** package manager (install via `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Ensure `~/.local/bin` is on `PATH` for `uv`

### Quick reference (all commands from repo root)

| Task | Command |
|------|---------|
| Install deps | `uv sync --dev` |
| Lint | `uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix` |
| Format | `uv run ruff --config dev/ruff.toml format ccbt/` |
| Type check | `uv run ty check --config-file=dev/ty.toml --output-format=concise` |
| Tests (fast) | `uv run pytest -c dev/pytest.ini tests/unit/core/test_bencode.py -v --tb=short --timeout=30` |
| Tests (full) | `uv run pytest -c dev/pytest.ini tests/ -v --tb=short --maxfail=5 --timeout=60` |
| Run CLI | `uv run btbt <command>` or `uv run ccbt <torrent>` |

### Non-obvious caveats

- **`site/reports/` directory must exist** before running pytest. Create it with `mkdir -p site/reports` — pytest writes JUnit XML and logs there per `dev/pytest.ini`.
- **The full test suite is very large** (37 unit test subdirectories + integration/property/CLI/security/etc). Running all tests can exceed 5 minutes. For quick validation, run a focused subset like `tests/unit/core/test_bencode.py` (22 tests, ~45s).
- **Type check warnings about `ProactorEventLoop` and `ctypes.windll`** are expected on Linux — these are Windows-only code paths.
- **Lint has 5 pre-existing whitespace errors** in `ccbt/i18n/manager.py` (trailing whitespace on blank lines). These are in the existing codebase.
- **V1 torrent creation is not yet implemented** — use `--v2` or `--hybrid` flags with `btbt create-torrent`.
- **Config files live in `dev/`**, not the project root. Always pass `--config dev/ruff.toml`, `-c dev/pytest.ini`, etc.
