# Development Guide

This guide covers local development setup for contributors and developers who want to build and test changes locally.

## Prerequisites

- Docker and Docker Compose
- pre-commit (for code quality checks)

## Local Development Setup

### Clone and Configure

```bash
git clone https://github.com/mrgeetv/youtube-webcam-aggregator.git
cd youtube-webcam-aggregator

# Copy environment template
cp .env.example .env

# Edit .env and add your YouTube API key
```

### Using Docker Compose

Docker Compose is recommended for local development as it rebuilds from source:

```bash
# Start the service
docker compose up -d

# View logs
docker compose logs -f

# Restart after code changes
docker compose down && docker compose up -d --build
```

**Playlist URL:** `http://localhost:23457/playlist.m3u8`

### Environment Variables

Configure these in your `.env` file or pass directly to docker-compose:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `YOUTUBE_API_KEY` | (required) | YouTube Data API v3 key |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `UPDATE_INTERVAL_HOURS` | `5` | Hours between playlist refresh cycles |
| `MAX_VIDEOS_PER_CYCLE` | `1000` | Maximum videos to process per cycle (memory limit) |
| `CONCURRENT_EXTRACTIONS` | `5` | Parallel yt-dlp extractions (lower if hitting 429s) |
| `EXCLUDED_CATEGORIES` | `Gaming,Sports,Film & Animation,Howto & Style` | YouTube categories to exclude |
| `SEARCH_QUERY` | (see docker-compose.yml) | Search terms for finding live webcams |

### Using the Run Script

A helper script is provided for common operations:

```bash
# Build and run with cache
scripts/run.sh

# Build without cache (clean build)
scripts/run.sh --no-cache
```

## Docker Hardened Images (DHI)

This project uses [Docker Hardened Images](https://www.docker.com/blog/docker-hardened-images-for-every-developer/) in CI/production for enhanced security. DHI images are minimal, pre-hardened containers with reduced attack surface.

### Local Development

Local development uses standard Python images (no authentication required). The `docker-compose.yml` overrides the Dockerfile defaults to use `python:3.14-slim`:

```bash
docker compose up -d
```

### CI/Production

CI builds use DHI images from `dhi.io`, requiring authentication. Repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` must be configured in GitHub.

### Image Variants

| Stage   | Image                                    | Purpose                                  |
|---------|------------------------------------------|------------------------------------------|
| Build   | `dhi.io/python:3.14-alpine3.22-sfw-dev`  | Has pip for installing dependencies      |
| Runtime | `dhi.io/python:3.14-alpine3.22`          | Minimal, no pip (reduced attack surface) |

## Pre-commit Hooks

This project uses pre-commit hooks for code quality. Install them before making changes:

```bash
pip install pre-commit
pre-commit install
```

Hooks will run automatically on commit, checking:

- Python formatting (black)
- Python linting (flake8)
- Shell script validation (shellcheck)
- Dockerfile linting (hadolint)
- Markdown formatting (markdownlint)
- Conventional commit messages

To run hooks manually:

```bash
pre-commit run --all-files
```

## Project Structure

```text
youtube-webcam-aggregator/
├── src/                    # Python source code
│   └── get_streams.py      # Main application
├── scripts/                # Helper scripts
│   ├── run.sh              # Docker build/run script
│   └── check-python-version.sh
├── .github/workflows/      # CI/CD pipelines
├── Dockerfile              # Container definition
├── docker-compose.yml      # Development compose file
├── requirements.txt        # Python dependencies
└── requirements-dev.txt    # Development dependencies
```

## Port Configuration

- **Internal port:** 8000 (hardcoded in Python application)
- **Docker Compose port:** 23457 (mapped from 8000)

The HTTP server uses a custom handler serving only `/playlist.m3u8` and `/health` endpoints.

## Debugging

### Log Levels

Set `LOG_LEVEL` in your `.env` file to control logging verbosity:

```bash
# In .env file
LOG_LEVEL=DEBUG
```

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### Memory Tracking

When `LOG_LEVEL=DEBUG`, memory usage is logged at:

- Start and end of each scrape cycle
- After each batch of 50 videos processed

Example output:

```text
2024-01-15 10:30:00 DEBUG [webcam-scraper] Memory: 145 MB
```

This helps identify memory leaks from yt-dlp.

### Viewing Debug Logs

```bash
# Ensure LOG_LEVEL=DEBUG is set in .env, then restart
docker compose down && docker compose up -d

# View logs
docker compose logs -f
```

## Making Changes

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a feature branch from `main`
4. Make your changes
5. Ensure pre-commit hooks pass
6. Test locally with Docker Compose
7. Push to your fork and submit a pull request

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Format:

```text
type(scope): description
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`

Scopes: `docker`, `api`, `playlist`, `config`, `deps`, `ci`, `docs`
