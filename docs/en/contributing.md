# Contributing to ccBitTorrent

Thank you for your interest in contributing to ccBitTorrent! This document outlines the development process, code standards, and contribution workflow.

## Project Overview

ccBitTorrent is a high-performance BitTorrent client implementation in Python. This is a **reference Python implementation** licensed under the **GPL**. The project aims to provide a complete, well-tested, and performant BitTorrent client.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- [UV](https://github.com/astral-sh/uv) package manager (recommended)
- Git

### Initial Setup

1. Clone the repository:
```bash
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
```

2. Install dependencies using UV:
```bash
uv sync --dev
```

3. Install pre-commit hooks:
```bash
uv run pre-commit install --config dev/pre-commit-config.yaml
```

## Code Quality Standards

### Linting

We use [Ruff](https://github.com/astral-sh/ruff) for fast linting and formatting. Configuration is in [dev/ruff.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ruff.toml).

Run linting:
```bash
uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
```

Format code:
```bash
uv run ruff --config dev/ruff.toml format ccbt/
```

### Type Checking

We use [Ty](https://github.com/astral-sh/ty) for fast type checking. Configuration is in [dev/ty.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ty.toml).

Run type checking:
```bash
uv run ty check --config-file=dev/ty.toml --output-format=concise
```

### Testing

We use [pytest](https://pytest.org/) for testing. Configuration is in [dev/pytest.ini](https://github.com/ccBittorrent/ccbt/blob/main/dev/pytest.ini).

Run all tests:
```bash
uv run pytest -c dev/pytest.ini tests/ -v
```

Run with coverage:
```bash
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html --cov-report=xml
```

### Pre-commit Hooks

All quality checks run automatically via pre-commit hooks configured in [dev/pre-commit-config.yaml](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml). This includes:

- Ruff linting and formatting
- Ty type checking
- Bandit security scanning
- Pytest with coverage
- Benchmark smoke tests
- Version validation: Ensures version consistency between `pyproject.toml` and `ccbt/__init__.py`
- Changelog validation: Ensures `dev/CHANGELOG.md` is updated for code changes
- MkDocs build validation: `uv run mkdocs build -f dev/mkdocs.yml`
- Translation validation: `uv run python -m ccbt.i18n.scripts.validate_po`
- Translation coverage check: `uv run python -m ccbt.i18n.scripts.check_string_coverage --source-dir ccbt`

Run manually:
```bash
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
```

!!! note "Translation Verification"
    Before committing changes that affect translatable strings:
    1. Regenerate the `.pot` template: `uv run python -m ccbt.i18n.scripts.extract`
    2. Verify PO files: `uv run python -m ccbt.i18n.scripts.validate_po`
    3. Check translation coverage: `uv run python -m ccbt.i18n.scripts.check_string_coverage --source-dir ccbt`

## Development Configuration

All development configuration files are located in [dev/](dev/):

- [dev/pre-commit-config.yaml](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml) - Pre-commit hook configuration
- [dev/ruff.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ruff.toml) - Ruff linting and formatting
- [dev/ty.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ty.toml) - Type checking configuration
- [dev/pytest.ini](https://github.com/ccBittorrent/ccbt/blob/main/dev/pytest.ini) - Test configuration
- [dev/mkdocs.yml](https://github.com/ccBittorrent/ccbt/blob/main/dev/mkdocs.yml) - Documentation configuration

## Branch Strategy

### Main Branch

- The `main` branch is used for releases
- Only accepts merges from the `dev` branch
- Builds releases automatically on push to main

### Dev Branch

- The `dev` branch is the primary development branch
- **Only branch that merges to main**
- Runs all checks identically to main, including:
  - All linting and type checking
  - Full test suite with coverage
  - All benchmark checks from [dev/pre-commit-config.yaml:39-68](https://github.com/yourusername/ccbittorrent/blob/main/dev/pre-commit-config.yaml#L39-L68)
  - Documentation builds

### Feature Branches

Create feature branches directly from:
- **Sub-issues**: Branch directly from sub-issues if working on a specific part
- **Main issues**: Branch from main issues if addressing the full scope
- **GitHub Templates**: Use the GitHub issue template to create issues, then create a branch via the GitHub UI

## Issue Workflow

### Discussions

Development areas and features are discussed in GitHub Discussions. From these discussions come:

1. **Main Issues**: High-level feature or improvement requests
2. **Sub Issues**: Specific tasks or components related to a main issue

### Creating Issues

1. Use the GitHub issue template provided
2. Link to related discussions if applicable
3. Create issues for main features or sub-tasks as needed

### Branch Creation

- Create branches directly on sub-issues or main issues using GitHub UI
- Branch names should be descriptive and reference the issue number
- Example: `feature/dht-improvements-123` or `fix/peer-connection-bug-456`

## Contribution Process

### Making Changes

1. **Fork or create branch**: Create a branch from the appropriate issue
2. **Make changes**: Follow code quality standards
3. **Update Changelog**: Add your changes to `dev/CHANGELOG.md` in the appropriate section with format: `"- Description (YourName, ccBitTorrent contributors)"`
4. **Test locally**: Run all checks before pushing:
   ```bash
   uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
   ```
5. **Commit**: Use conventional commit messages
6. **Push**: Push to your branch
7. **Create PR**: Submit a pull request to the `dev` branch

### Changelog Requirements

All code changes must be documented in `dev/CHANGELOG.md`. This is automatically validated by pre-commit hooks and CI/CD.

**Changelog Entry Format:**
- Single-line entries only
- Format: `"- Description (YourName, ccBitTorrent contributors)"`
- Add entries to the appropriate section:
  - **Exciting New Features 🎉**: New features and enhancements
  - **Bug Fixes 🐛**: Bug fixes and corrections
  - **Security 🔒**: Security improvements
  - **Performance ⚡**: Performance optimizations
  - **Documentation 📚**: Documentation updates
  - **Dependencies 📦**: Dependency updates
  - **Internal 🔧**: Refactoring and internal improvements

**Example:**
```markdown
### Exciting New Features 🎉
- Added support for BitTorrent Protocol v2 (YourName, ccBitTorrent contributors)
```

**Note:** Documentation-only changes (updating docs, translations, etc.) do not require changelog entries. The validation script automatically skips these.

### Automated Checks

When you create a pull request, CI/CD will automatically:

1. **Digital CLA Signature**: Contributors are expected to digitally sign a CLA in CI/CD
2. Run all linting checks (Ruff) - See [Lint Workflow](CI_CD.md#lint-workflow-githubworkflowslintyml)
3. Run type checking (Ty) - See [Lint Workflow](CI_CD.md#lint-workflow-githubworkflowslintyml)
4. Validate version consistency - Ensures `pyproject.toml` and `ccbt/__init__.py` versions match
5. Validate changelog - Ensures `dev/CHANGELOG.md` is updated for code changes
6. Run full test suite with coverage requirements - See [Test Workflow](CI_CD.md#test-workflow-githubworkflowstestyml)
7. Run benchmark smoke tests - See [Benchmark Workflow](CI_CD.md#benchmark-workflow-githubworkflowsbenchmarkyml)
8. Build documentation - See [Documentation Workflow](CI_CD.md#documentation-workflow-githubworkflowsdocsyml)
9. Check code coverage thresholds - See [Coverage Requirements](CI_CD.md#coverage-requirements)

For detailed CI/CD documentation, see [CI/CD Documentation](CI_CD.md).

### Code Coverage

We maintain high code coverage standards. Coverage reports are generated and must meet minimum thresholds. View coverage reports in [reports/coverage.md](reports/coverage.md).

### Benchmark Requirements

Benchmark checks from [dev/pre-commit-config.yaml:39-68](https://github.com/yourusername/ccbittorrent/blob/main/dev/pre-commit-config.yaml#L39-L68) must pass. These include:

- Hash verification benchmarks
- Disk I/O benchmarks
- Piece assembly benchmarks
- Loopback throughput benchmarks

If benchmarks fail, the contribution may need optimization or discussion.

## Project Maintenance

### Automatic Acceptance

Contributions that pass all automated checks (linting, type checking, tests, benchmarks, coverage) are typically accepted automatically unless:

- Benchmarks fail (may require optimization)
- Conflicts with project direction (rare)
- Security concerns (handled separately)

### Manual Review

Maintainers may manually review for:
- Architecture alignment
- Performance implications
- Security considerations
- Documentation quality

## Documentation Standards

- All public APIs must be documented
- Use Google-style docstrings
- Keep documentation up-to-date with code changes
- Build documentation locally: `uv run mkdocs build --strict -f dev/mkdocs.yml`
- Documentation source is in [docs/](docs/)

### Contributing Documentation

When contributing to documentation:

1. **Update Existing Docs**: Keep documentation synchronized with code changes
2. **Add New Docs**: Create new documentation pages as needed
3. **Test Builds**: Always test documentation builds locally before submitting
4. **Follow Style**: Maintain consistency with existing documentation style
5. **Check Links**: Verify all internal and external links work correctly

Documentation is built automatically in CI/CD. See [Documentation Workflow](CI_CD.md#documentation-workflow-githubworkflowsdocsyml) for details.

### Contributing Blog Posts

We welcome blog post contributions! Blog posts are located in `docs/blog/`.

**Creating a Blog Post:**

1. Create a new markdown file in `docs/blog/` with the format: `YYYY-MM-DD-slug.md`
2. Include frontmatter:
   ```yaml
   ---
   title: Your Post Title
   date: YYYY-MM-DD
   author: Your Name
   tags:
     - tag1
     - tag2
   ---
   ```
3. Use `<!-- more -->` to separate the excerpt from the full content
4. Follow the existing blog post style and format
5. Test the blog post appears correctly in the documentation build

**Blog Post Guidelines:**

- Keep posts relevant to ccBitTorrent
- Use clear, engaging language
- Include code examples where appropriate
- Add relevant tags for discoverability
- Link to related documentation when helpful

### Contributing Translations

Help make ccBitTorrent accessible to users worldwide by contributing translations!

**Translation Process:**

1. **Choose a Language**: Pick a language from the supported list (see [Translation Guide](i18n/translation-guide.md))
2. **Select Content**: Choose documentation pages to translate
3. **Create Translation**: Translate content while maintaining:
   - Markdown formatting
   - Code examples (keep in original language)
   - File structure
   - Link structure
4. **Test Build**: Verify translations work in the documentation build
5. **Submit PR**: Create a pull request with your translations

**Translation Guidelines:**

- Maintain technical accuracy
- Keep code examples in original language
- Update internal links to translated versions
- Follow the [Translation Guide](i18n/translation-guide.md) for detailed instructions
- Test language switcher functionality

For detailed translation instructions, see the [Translation Guide](i18n/translation-guide.md).

## License

This project is licensed under the **GPL** (GNU General Public License). By contributing, you agree that your contributions will be licensed under the same license.

## Getting Help

- **Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and design discussions
- **Code Review**: All PRs receive code review from maintainers

## Recognition

Contributors are recognized for their valuable contributions. Significant contributions may be highlighted in release notes and project documentation.

Thank you for contributing to ccBitTorrent!

**Creating a Blog Post:**

1. Create a new markdown file in `docs/blog/` with the format: `YYYY-MM-DD-slug.md`
2. Include frontmatter:
   ```yaml
   ---
   title: Your Post Title
   date: YYYY-MM-DD
   author: Your Name
   tags:
     - tag1
     - tag2
   ---
   ```
3. Use `<!-- more -->` to separate the excerpt from the full content
4. Follow the existing blog post style and format
5. Test the blog post appears correctly in the documentation build

**Blog Post Guidelines:**

- Keep posts relevant to ccBitTorrent
- Use clear, engaging language
- Include code examples where appropriate
- Add relevant tags for discoverability
- Link to related documentation when helpful

### Contributing Translations

Help make ccBitTorrent accessible to users worldwide by contributing translations!

**Translation Process:**

1. **Choose a Language**: Pick a language from the supported list (see [Translation Guide](i18n/translation-guide.md))
2. **Select Content**: Choose documentation pages to translate
3. **Create Translation**: Translate content while maintaining:
   - Markdown formatting
   - Code examples (keep in original language)
   - File structure
   - Link structure
4. **Test Build**: Verify translations work in the documentation build
5. **Submit PR**: Create a pull request with your translations

**Translation Guidelines:**

- Maintain technical accuracy
- Keep code examples in original language
- Update internal links to translated versions
- Follow the [Translation Guide](i18n/translation-guide.md) for detailed instructions
- Test language switcher functionality

For detailed translation instructions, see the [Translation Guide](i18n/translation-guide.md).

## License

This project is licensed under the **GPL** (GNU General Public License). By contributing, you agree that your contributions will be licensed under the same license.

## Getting Help

- **Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and design discussions
- **Code Review**: All PRs receive code review from maintainers

## Recognition

Contributors are recognized for their valuable contributions. Significant contributions may be highlighted in release notes and project documentation.

Thank you for contributing to ccBitTorrent!

**Creating a Blog Post:**

1. Create a new markdown file in `docs/blog/` with the format: `YYYY-MM-DD-slug.md`
2. Include frontmatter:
   ```yaml
   ---
   title: Your Post Title
   date: YYYY-MM-DD
   author: Your Name
   tags:
     - tag1
     - tag2
   ---
   ```
3. Use `<!-- more -->` to separate the excerpt from the full content
4. Follow the existing blog post style and format
5. Test the blog post appears correctly in the documentation build

**Blog Post Guidelines:**

- Keep posts relevant to ccBitTorrent
- Use clear, engaging language
- Include code examples where appropriate
- Add relevant tags for discoverability
- Link to related documentation when helpful

### Contributing Translations

Help make ccBitTorrent accessible to users worldwide by contributing translations!

**Translation Process:**

1. **Choose a Language**: Pick a language from the supported list (see [Translation Guide](i18n/translation-guide.md))
2. **Select Content**: Choose documentation pages to translate
3. **Create Translation**: Translate content while maintaining:
   - Markdown formatting
   - Code examples (keep in original language)
   - File structure
   - Link structure
4. **Test Build**: Verify translations work in the documentation build
5. **Submit PR**: Create a pull request with your translations

**Translation Guidelines:**

- Maintain technical accuracy
- Keep code examples in original language
- Update internal links to translated versions
- Follow the [Translation Guide](i18n/translation-guide.md) for detailed instructions
- Test language switcher functionality

For detailed translation instructions, see the [Translation Guide](i18n/translation-guide.md).

## License

This project is licensed under the **GPL** (GNU General Public License). By contributing, you agree that your contributions will be licensed under the same license.

## Getting Help

- **Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and design discussions
- **Code Review**: All PRs receive code review from maintainers

## Recognition

Contributors are recognized for their valuable contributions. Significant contributions may be highlighted in release notes and project documentation.

Thank you for contributing to ccBitTorrent!

**Creating a Blog Post:**

1. Create a new markdown file in `docs/blog/` with the format: `YYYY-MM-DD-slug.md`
2. Include frontmatter:
   ```yaml
   ---
   title: Your Post Title
   date: YYYY-MM-DD
   author: Your Name
   tags:
     - tag1
     - tag2
   ---
   ```
3. Use `<!-- more -->` to separate the excerpt from the full content
4. Follow the existing blog post style and format
5. Test the blog post appears correctly in the documentation build

**Blog Post Guidelines:**

- Keep posts relevant to ccBitTorrent
- Use clear, engaging language
- Include code examples where appropriate
- Add relevant tags for discoverability
- Link to related documentation when helpful

### Contributing Translations

Help make ccBitTorrent accessible to users worldwide by contributing translations!

**Translation Process:**

1. **Choose a Language**: Pick a language from the supported list (see [Translation Guide](i18n/translation-guide.md))
2. **Select Content**: Choose documentation pages to translate
3. **Create Translation**: Translate content while maintaining:
   - Markdown formatting
   - Code examples (keep in original language)
   - File structure
   - Link structure
4. **Test Build**: Verify translations work in the documentation build
5. **Submit PR**: Create a pull request with your translations

**Translation Guidelines:**

- Maintain technical accuracy
- Keep code examples in original language
- Update internal links to translated versions
- Follow the [Translation Guide](i18n/translation-guide.md) for detailed instructions
- Test language switcher functionality

For detailed translation instructions, see the [Translation Guide](i18n/translation-guide.md).

## License

This project is licensed under the **GPL** (GNU General Public License). By contributing, you agree that your contributions will be licensed under the same license.

## Getting Help

- **Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and design discussions
- **Code Review**: All PRs receive code review from maintainers

## Recognition

Contributors are recognized for their valuable contributions. Significant contributions may be highlighted in release notes and project documentation.

Thank you for contributing to ccBitTorrent!
