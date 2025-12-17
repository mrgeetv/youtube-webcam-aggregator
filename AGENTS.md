# Project: YouTube Live Webcam Aggregator

## Branching Workflow

For any new work (fixes, features, chores, etc.):

1. Pull latest main
2. Create new branch from main
3. Make changes and commit

## Conventional Commit Format

Format: `type(scope): description`

### Commit Types

**Release types** (trigger version bumps):

- `feat` - New feature (minor version bump)
- `fix` - Bug fix (patch version bump)
- `perf` - Performance improvement (patch version bump)
- `revert` - Revert previous change (patch version bump)
- `refactor` - Code refactoring (patch version bump)

**Non-release types** (no version bump):

- `docs` - Documentation changes
- `style` - Code style/formatting
- `chore` - Maintenance tasks
- `test` - Test changes
- `build` - Build system changes
- `ci` - CI/CD changes

### Valid Scopes

- `docker` - Dockerfile, docker-compose.yml
- `api` - YouTube API integration
- `playlist` - M3U8 playlist generation
- `scraper` - Stream extraction, yt-dlp, memory management
- `config` - Environment variables, configuration
- `deps` - Dependency updates
- `ci` - CI/CD workflows, automation
- `docs` - Documentation, README

## Dependency Version Research

When adding or updating versioned dependencies (Python packages, GitHub Actions, pre-commit hooks, Docker images, etc.):

1. Find the GitHub repo (WebSearch if URL unknown)
2. Get latest version using one of:
   - `gh release list --repo owner/repo --limit 5` (preferred when repo is known)
   - WebFetch on GitHub releases page (fallback)
3. If version cannot be verified from GitHub, stop and ask user to confirm

## Pre-commit Behavior

When pre-commit finds issues:

- **Never automatically fix them**
- Always present the issues to the user first
- Let the user decide whether to fix, ignore, or configure exceptions
- This includes: file permissions, line length violations, formatting issues, etc.

## Bash Script Best Practices

Always use modern bash syntax:

- Use `[[ ]]` instead of `[ ]` for test conditions
- Use `$(command)` instead of backticks
- Quote all variable expansions: `"$var"`
- Use `#!/bin/bash` shebang

## CLAUDE.md Documentation Rules

When updating this file:

- **Never duplicate information** - check existing sections before adding new content
- **Reorganize instead of duplicating** - if information exists but is unclear, reorganize or clarify existing sections
- **Add only project-specific information** - valid scopes, project-specific tools, version constraints

## Code Quality Tools

Pre-commit hooks enforced:

- **black** - Python code formatting
- **flake8** - Python linting (ignores: E501, E203)
- **shellcheck** - Shell script validation (severity: warning)
- **markdownlint-cli2** - Markdown formatting (CHANGELOG.md excluded)
- **hadolint** - Dockerfile linting
- **conventional-pre-commit** - Commit message validation (strict mode with forced scopes)
- **check-python-version** - Custom validation that .python-version matches Dockerfile

## Python Version Synchronization

This project enforces Python version consistency:

- `.python-version` - Source of truth (currently 3.14)
- `Dockerfile` - Must use `FROM python:{version}-slim` matching .python-version
- Pre-commit hook validates synchronization automatically
- CI uses .python-version for GitHub Actions Python setup

**When updating Python version:**

1. Update `.python-version` file
2. Update `Dockerfile` FROM line to match
3. Pre-commit hook validates consistency
4. Test Docker build before committing
