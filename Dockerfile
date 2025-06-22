FROM python:3-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy source code
COPY src/ ./src/

WORKDIR /app/src

# Run the script
CMD ["python3", "get_streams.py"]
