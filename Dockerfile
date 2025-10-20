# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPINE_DB_PATH=/app/spine_dev.sqlite3 \
    DEFAULT_ORG_ID=org_demo

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire meeting-agent code
COPY . ./

# Make startup script executable
RUN chmod +x startup.sh

EXPOSE 8000

# Use smart startup script that handles both SQLite and MongoDB modes
CMD ["./startup.sh"]
