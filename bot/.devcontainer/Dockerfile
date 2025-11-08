# Use official Python runtime as base image
FROM mcr.microsoft.com/devcontainers/python:3.11-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1 \
	PIP_NO_CACHE_DIR=1 \
	PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	libpq-dev \
	postgresql-client \
	redis-tools \
	git \
	curl \
	wget \
	vim \
	nano \
	tmux \
	htop \
	jq \
	netcat-traditional \
	dnsutils \
	iputils-ping \
	&& rm -rf /var/lib/apt/lists/*

# Create vscode user if it doesn't exist (for compatibility)
RUN if ! id -u vscode > /dev/null 2>&1; then \
	useradd -m -s /bin/bash vscode; \
	fi

# Set working directory
WORKDIR /workspace

# Install Python development tools
RUN pip install --upgrade pip setuptools wheel

# Copy only requirements to cache layer
COPY requirements.txt .

# Install project dependencies
RUN pip install -r requirements.txt

# Copy the rest of the project
COPY . .

# Create necessary directories
RUN mkdir -p /workspace/logs \
	&& mkdir -p /workspace/data \
	&& mkdir -p /workspace/reports \
	&& mkdir -p /workspace/backups

# Make scripts executable
RUN chmod +x .devcontainer/*.sh || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
	CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["sleep", "infinity"]
