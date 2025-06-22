#!/bin/bash

# Stop any existing containers
docker compose down

# Build, optionally without cache
if [ "$1" == "--no-cache" ]; then
    echo "Building without cache..."
    docker compose build --force-rm  # <-- Use --force-rm
else
    echo "Building with cache..."
    docker compose build
fi

# Run the container
docker compose up -d

# Follow logs
docker compose logs -f
