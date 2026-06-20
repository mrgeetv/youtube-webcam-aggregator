# Project: Live Webcam Aggregator (multi-source, v2)

> **Note**: CLAUDE.md is a symlink to this file. Edit AGENTS.md only.

## Development Context

@DEVELOPMENT.md

## Architecture & Extension Points (v2)

The app is two phases, decoupled by a catalogue snapshot:

1. **Catalogue build** (`catalogue.py`, every `CATALOGUE_INTERVAL_HOURS`): each
   `Source.discover()` yields `Candidate`s → liveness filter (YouTube via the Data
   API batch; everything else via a **fetch-verified probe** — `make_is_alive`
   actually fetches the HLS manifest and drops dead/404 and DASH cams) → per-source
   empty-guard (keeps the last good set if a source collapses ≥50%, needs 2 bad
   cycles to accept) → cross-source `dedupe()` (per-field merge) → YouTube cams get
   their category from the Data API; scraped titles get location appended
   (`with_location`) → `CatalogueEntry`s with a stable id.
2. **On-demand serve** (`serving.py` + `app.py` handler): the playlist holds stable
   `/stream/<id>` URLs. On play, `ResolveCache` resolves the upstream via the
   `Registry`→`Extractor`, and the HLS manifest is proxied — child manifests rewritten
   through `/stream/<id>/m?u=…&sig=…`. Segments go **direct to the CDN by default**,
   with two per-host exceptions (their tokens are IP-bound to the fetcher):
   `_DIRECT_PLAYBACK_HOSTS` (pixelcaster) get a **302 passthrough** so the player
   fetches the whole chain itself; `_PROXY_SEGMENT_HOSTS` (balticlivecam) get their
   **segments relayed** through `/stream/<id>/s?u=…&sig=…`.

**`build_app()` in `app.py` is the wiring seam.** To extend:

- **Add a source** — implement the `Source` protocol (`sources/base.py`): a `name`
  and `discover() -> Iterable[Candidate]`. HTML sources subclass the scraper base and
  reuse the extraction ladder. Add the instance to `active_sources` in `build_app`.
  Set `Candidate.predisc_key` so dedup can merge it (`yt:<id>` for YouTube,
  `hls:<normalised>` for direct m3u8, `None` = never merged).
- **Add an extractor** — implement the `Extractor` protocol (`extractors/base.py`):
  `resolve(target_url) -> Resolved(url, stream_type, ttl_seconds)`. Add it to the
  `extractors` dict in `build_app` AND a predicate to `build_registry` (startup
  validation raises if a rule names an extractor not in the dict). If the CDN's
  tokens are IP-bound, ALSO add its host to `_DIRECT_PLAYBACK_HOSTS` (passthrough)
  or `_PROXY_SEGMENT_HOSTS` (segment relay) in `serving.py`, or segments will 403.
- **Category mapping** lives in `categories.py` (`_MAP`); YouTube categories come
  from the Data API (`videos.list` categoryId) and pass through, everything else
  maps to the unified taxonomy or "Other".

**Hard-won lessons (don't relearn these):**

- Route ipcamlive **`player/player.php` URLs only** to the resolver; direct
  `s*.ipcamlive.com/.../stream.m3u8` (the majority) must fall through to `DirectHls`.
- Baltic's admin-ajax POST needs `Referer` = the **site origin** (`origin_of`), not
  the ajax URL — wrong Referer 403s silently.
- YouTube extraction needs the deno/yt-dlp-ejs stack (the n-challenge); the Dockerfile
  patches deno's ELF interpreter so it runs on the hardened Alpine runtime — leave it.
- Liveness is a **build-time** probe (the playlist must not list dead cams); the
  serve-time resolve is separate and fresh (tokens expire). Don't merge them.
- yt-dlp is forced to an **HLS** format (`-f b[protocol*=m3u8]`) — some live streams
  default to DASH (`.mpd`) which the HLS proxy can't serve; `serve_stream` rejects
  any non-`#EXTM3U` body (so DASH-only cams are dropped, not served broken).

**Security model:** every outbound fetch goes through `fetch.is_safe_url` (rejects
non-http(s) and private/loopback/link-local IPs), an 8 MB cap, and **per-hop redirect
re-validation** (in both the `requests` `Fetcher` and the `urllib` `_OPENER`); proxied
`/m` and `/s` URLs are HMAC-signed (`signing.py`) so only server-emitted URLs are
fetched. **Known residuals** (mitigate by running behind your own network controls):
(1) **DNS-rebinding TOCTOU** — `is_safe_url` resolves, then the HTTP lib re-resolves
at connect; durable fix = connection-level IP pinning. (2) **egress-proxy surface** —
the proxy will sign + fetch any *public* host that appears in an upstream manifest;
durable fix = a CDN-host allowlist on the rewritten `/m`/`/s` URLs.

**Tests:** files are `*_test.py` (the `name-tests-test` hook rejects `test_*.py`).
The suite is **fully offline** — no real-endpoint/live tests (sources, resolvers,
and the HTTP handler are exercised with injected fakes + real sockets on port 0).
The gate is `pre-commit` (which runs `pytest` + a coverage floor as a `files:`-gated
hook) plus the same checks in CI — not ruff/mypy. The `pytest` hook calls `pytest`
directly, so the dev venv must be on `PATH` when committing.

## Branching Workflow

For any new work (fixes, features, chores, etc.):

1. Pull latest main
2. Create new branch from main
3. Make changes and commit

A Claude Code `PreToolUse` hook in `.claude/settings.json` enforces this
by blocking `git commit` when the current branch is `main` or `master`.
The hook script lives at `.claude/hooks/block-commit-to-main.sh`.

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
- **check-python-version** - Custom validation that .python-version matches Dockerfile, docker-compose.yml, and pyrightconfig.json
- **basedpyright** - Python type checking (stricter pyright fork with pylance features)
- **pytest** - Full test suite + coverage floor (`--cov-fail-under`); runs when `src/`, `tests/`, or `requirements*.txt` change. Calls `pytest` directly, so the dev venv must be on `PATH` when committing. Also runs in CI.

## Python Version Synchronization

This project enforces Python version consistency:

- `.python-version` - Source of truth (currently 3.14)
- `Dockerfile` - `ARG RUNTIME_IMAGE` default must use `dhi.io/python:{version}-alpine3.24`
- `docker-compose.yml` - `RUNTIME_IMAGE` build arg must use `python:{version}-slim`
- `pyrightconfig.json` - Must have `pythonVersion` matching .python-version
- Pre-commit hook validates synchronization automatically
- CI uses .python-version for GitHub Actions Python setup

**When updating Python version:**

1. Update `.python-version` file
2. Update `Dockerfile` `ARG RUNTIME_IMAGE` and `ARG BUILD_IMAGE` defaults to match
3. Update `docker-compose.yml` `RUNTIME_IMAGE` and `BUILD_IMAGE` args to match
4. Update `pyrightconfig.json` pythonVersion to match
5. Pre-commit hook validates consistency
6. Test Docker build before committing
