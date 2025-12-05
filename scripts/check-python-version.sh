#!/bin/bash
# Pre-commit hook to validate .python-version matches Dockerfile Python version

PYTHON_VERSION_FILE=".python-version"
DOCKERFILE="Dockerfile"

# Read Python version from .python-version
if [[ ! -f "$PYTHON_VERSION_FILE" ]]; then
    echo "Error: $PYTHON_VERSION_FILE not found"
    exit 1
fi

EXPECTED_VERSION=$(cat "$PYTHON_VERSION_FILE" | tr -d '\n\r')

# Extract Python version from Dockerfile
if [[ ! -f "$DOCKERFILE" ]]; then
    echo "Error: $DOCKERFILE not found"
    exit 1
fi

# Look for python:X.Y or python:X.Y-slim pattern in FROM line
DOCKERFILE_VERSION=$(grep -E '^FROM python:' "$DOCKERFILE" | sed -E 's/^FROM python:([0-9]+\.[0-9]+).*/\1/')

if [[ -z "$DOCKERFILE_VERSION" ]]; then
    echo "Error: Could not extract Python version from $DOCKERFILE"
    echo "Expected pattern: FROM python:X.Y or FROM python:X.Y-slim"
    exit 1
fi

if [[ "$EXPECTED_VERSION" != "$DOCKERFILE_VERSION" ]]; then
    echo "❌ Python version mismatch!"
    echo "  .python-version: $EXPECTED_VERSION"
    echo "  Dockerfile:      $DOCKERFILE_VERSION"
    echo ""
    echo "Fix: Update Dockerfile to use python:${EXPECTED_VERSION}-slim"
    exit 1
fi

echo "✅ Python versions match: $EXPECTED_VERSION"
exit 0
