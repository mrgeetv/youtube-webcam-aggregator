# Build arguments for image selection (defaults to DHI)
ARG BUILD_IMAGE=dhi.io/python:3.14-alpine3.22-sfw-dev
ARG RUNTIME_IMAGE=dhi.io/python:3.14-alpine3.22
ARG DENO_IMAGE=denoland/deno:bin-2.6.0

# Deno binary source (for yt-dlp YouTube extraction)
# See: https://github.com/yt-dlp/yt-dlp/wiki/EJS
FROM ${DENO_IMAGE} AS deno_src

# Stage 1: Build dependencies
FROM ${BUILD_IMAGE} AS builder

WORKDIR /app

# Copy requirements and install dependencies to isolated directory
COPY requirements.txt .
RUN pip3 install --no-cache-dir --target=/deps -r requirements.txt

# Stage 2: Runtime
FROM ${RUNTIME_IMAGE}

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/deps
ENV PATH="/deps/bin:$PATH"

WORKDIR /app

# Expose HTTP server port
EXPOSE 8000

# Install Deno runtime (required for yt-dlp YouTube extraction)
COPY --from=deno_src /deno /usr/local/bin/deno

# Copy installed dependencies from builder
COPY --from=builder /deps /deps

# Copy source code
COPY src/ ./src/

WORKDIR /app/src

# Health check (uses stdlib urllib - no curl/wget in DHI images)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python3", "get_streams.py"]
