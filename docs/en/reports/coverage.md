# Code Coverage Report

This page displays the code coverage report when available. On Read the Docs the report is not generated; use the coverage report in CI (e.g. Codecov) or generate it locally.

**Generate the report locally:** Run tests with coverage and HTML output:

```bash
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html
```

Then open `htmlcov/index.html` in your browser. When the docs are built in CI with coverage data, an embedded report may appear below.

<!-- mkdocs-coverage -->

The coverage report shows which lines of code are executed by the test suite, helping identify areas that need additional testing.

## Coverage Targets

- **Project-wide**: 99% coverage target
- **Patch/PR**: 90% coverage threshold
- **Changes**: 80% coverage threshold

See [contributing.md](../contributing.md) for more information about our coverage requirements.

