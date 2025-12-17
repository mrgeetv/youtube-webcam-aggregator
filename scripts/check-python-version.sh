#!/bin/bash
# Pre-commit hook to validate Python versions match across:
# - .python-version (source of truth)
# - Dockerfile ARG defaults (DHI images for CI)
# - docker-compose.yml build args (standard images for local dev)

PYTHON_VERSION_FILE=".python-version"
DOCKERFILE="Dockerfile"
COMPOSE_FILE="docker-compose.yml"

# Read expected version from .python-version
if [[ ! -f "$PYTHON_VERSION_FILE" ]]; then
    echo "Error: $PYTHON_VERSION_FILE not found"
    exit 1
fi
EXPECTED_VERSION=$(cat "$PYTHON_VERSION_FILE" | tr -d '\n\r')

# Check Dockerfile ARG RUNTIME_IMAGE default
if [[ ! -f "$DOCKERFILE" ]]; then
    echo "Error: $DOCKERFILE not found"
    exit 1
fi
DOCKERFILE_VERSION=$(grep -E '^ARG RUNTIME_IMAGE=.*python:' "$DOCKERFILE" | sed -E 's/.*python:([0-9]+\.[0-9]+).*/\1/')
if [[ -z "$DOCKERFILE_VERSION" ]]; then
    echo "Error: Could not extract Python version from $DOCKERFILE ARG RUNTIME_IMAGE"
    exit 1
fi
if [[ "$EXPECTED_VERSION" != "$DOCKERFILE_VERSION" ]]; then
    echo "❌ Python version mismatch in Dockerfile!"
    echo "  .python-version: $EXPECTED_VERSION"
    echo "  Dockerfile ARG:  $DOCKERFILE_VERSION"
    exit 1
fi

# Check docker-compose.yml RUNTIME_IMAGE build arg
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Error: $COMPOSE_FILE not found"
    exit 1
fi
COMPOSE_VERSION=$(grep -E 'RUNTIME_IMAGE:.*python:' "$COMPOSE_FILE" | sed -E 's/.*python:([0-9]+\.[0-9]+).*/\1/')
if [[ -z "$COMPOSE_VERSION" ]]; then
    echo "Error: Could not extract Python version from $COMPOSE_FILE RUNTIME_IMAGE"
    exit 1
fi
if [[ "$EXPECTED_VERSION" != "$COMPOSE_VERSION" ]]; then
    echo "❌ Python version mismatch in docker-compose.yml!"
    echo "  .python-version:      $EXPECTED_VERSION"
    echo "  docker-compose.yml:   $COMPOSE_VERSION"
    exit 1
fi

echo "✅ Python versions match: $EXPECTED_VERSION"
exit 0
