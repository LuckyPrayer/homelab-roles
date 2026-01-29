FROM node:20-slim AS claude-installer

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# ---

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ANTHROPIC_API_KEY="" \
    HOME=/home/oracle \
    PATH="/home/oracle/.npm-global/bin:/home/oracle/.local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    docker.io \
    nodejs \
    npm \
    openssh-client \
    iputils-ping \
    dnsutils \
    netcat-openbsd \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create oracle user and group (matching host UID/GID 3100)
RUN groupadd -g 3100 oracle && \
    useradd -m -u 3100 -g oracle -s /bin/bash oracle && \
    mkdir -p /home/oracle/.ssh /home/oracle/.npm-global && \
    chown -R oracle:oracle /home/oracle

# Install Claude Code CLI as oracle user
USER oracle
RUN npm config set prefix '/home/oracle/.npm-global' && \
    npm install -g @anthropic-ai/claude-code
USER root

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories and set ownership
RUN mkdir -p /app/logs /app/codebase && \
    chown -R oracle:oracle /app

# Switch to oracle user
USER oracle

# Configure Claude CLI for non-interactive use
# The API key will be passed via environment variable ANTHROPIC_API_KEY

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import discord; print('ok')" || exit 1

# Default command
CMD ["python", "main.py"]
