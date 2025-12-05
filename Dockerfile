FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Deno runtime (required for yt-dlp YouTube extraction)
# See: https://github.com/yt-dlp/yt-dlp/wiki/EJS
# Using official Deno binary image: https://github.com/denoland/deno_docker
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

WORKDIR /app/src

# Run the script
CMD ["python3", "get_streams.py"]
