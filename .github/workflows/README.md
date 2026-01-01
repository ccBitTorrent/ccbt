# CI/CD Workflow Overview

## Test Workflow (test.yml)
- **Triggers**: Push/PR to dev branch, workflow_dispatch
- **Purpose**: Run full test suite with coverage
- **Runs**: All tests except compatibility tests
- **Rationale**: Tests run on dev branch (development branch), avoiding duplicate runs when merging to main

## Documentation Workflow (build-documentation.yml)
- **Triggers**: Push/PR to main branch, workflow_dispatch
- **Purpose**: Build and deploy documentation
- **Runs**: 
  - Generate coverage report (for docs embedding)
  - Generate Bandit report (for docs embedding)
  - Build documentation
  - Deploy to GitHub Pages (main branch only)
- **Rationale**: 
  - Docs build on main (stable branch) when code is merged from dev
  - Coverage and Bandit reports are embedded in documentation
  - Main branch is where published docs live

## Security Workflow (security.yml)
- **Triggers**: Push/PR to main, weekly schedule, workflow_dispatch
- **Purpose**: Security scanning (Bandit, Safety)
- **Runs**: Security scans only

## Release Workflow (release.yml)
- **Triggers**: Tag push (v*), workflow_dispatch
- **Purpose**: Pre-release validation and release creation
- **Runs**: Full test suite, linting, type checking, security scans, documentation build

