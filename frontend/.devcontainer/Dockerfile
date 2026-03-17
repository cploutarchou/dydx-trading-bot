# Multi-stage build for dYdX Trading Bot Frontend DevContainer
# Optimized for Linux/WSL with React development tools
ARG VARIANT=20-bullseye
FROM node:${VARIANT}

# Set environment variables for better compatibility
ENV DEBIAN_FRONTEND=noninteractive \
	NODE_ENV=development \
	npm_config_loglevel=verbose \
	npm_config_update_notifier=false

# Install system dependencies (consolidated for smaller layers)
RUN apt-get update && apt-get install -y --no-install-recommends \
	git \
	curl \
	wget \
	build-essential \
	python3 \
	openssh-client \
	rsync \
	gnupg \
	lsb-release \
	ca-certificates \
	apt-transport-https \
	software-properties-common \
	libssl-dev \
	libffi-dev \
	libc6-dev \
	net-tools \
	procps \
	sudo \
	&& rm -rf /var/lib/apt/lists/*

# Install Docker CLI using the current container architecture
RUN install -m 0755 -d /etc/apt/keyrings && \
	curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
	chmod a+r /etc/apt/keyrings/docker.asc && \
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" > /etc/apt/sources.list.d/docker.list && \
	apt-get update && \
	apt-get install -y --no-install-recommends docker-ce-cli && \
	rm -rf /var/lib/apt/lists/*

# Install Docker Compose (with fallback for WSL)
RUN curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose 2>/dev/null || \
	curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-Linux-x86_64" -o /usr/local/bin/docker-compose && \
	chmod +x /usr/local/bin/docker-compose

# Install additional development tools
RUN npm install -g --no-audit --no-fund \
	pnpm \
	yarn \
	nodemon \
	2>&1 || true

# Configure node user with proper permissions
RUN usermod -aG docker node 2>/dev/null || echo "Docker group membership failed"

# Configure sudoers for node user (required by docker-init.sh)
RUN echo "node ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/node && \
	chmod 0440 /etc/sudoers.d/node

# Create necessary directories with proper permissions
RUN mkdir -p /home/node/.ssh /home/node/.local/bin /workspace/.npm /workspace/.tmp && \
	chmod 700 /home/node/.ssh && \
	chown -R node:node /home/node /workspace 2>/dev/null || true

# Configure npm for performance
RUN npm config set --global \
	fetch-timeout=300000 \
	fetch-retry-mintimeout=10000 \
	fetch-retry-maxtimeout=60000 \
	audit=false

# Install React Developer Tools globally (optional but useful)
RUN npm install -g --no-audit --no-fund \
	create-react-app \
	2>&1 || true

# Switch to node user for security
USER node

# Set working directory
WORKDIR /workspace

# Set PATH to include local bin
ENV PATH="/home/node/.local/bin:${PATH}"

# Verify installation
RUN node --version && npm --version && git --version

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
	CMD node --version || exit 1

# Default command: keep container alive for DevContainer sessions
CMD ["sleep", "infinity"]
