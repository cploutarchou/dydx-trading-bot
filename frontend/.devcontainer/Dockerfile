# Multi-stage build for dYdX Trading Bot Frontend DevContainer
FROM node:20-bullseye

# Install system dependencies
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
	&& rm -rf /var/lib/apt/lists/*

# Install Docker CLI (to run docker commands from inside container)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add - && \
	add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable" && \
	apt-get update && \
	apt-get install -y docker-ce-cli && \
	rm -rf /var/lib/apt/lists/*

# Install Docker Compose
RUN curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && \
	chmod +x /usr/local/bin/docker-compose

# Add existing node user to sudoers (user already exists in node:20-bullseye)
RUN echo "node ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Setup SSH directory for node user
RUN mkdir -p /home/node/.ssh && \
	chmod 700 /home/node/.ssh && \
	chown -R node:node /home/node/.ssh

# Setup .gitconfig to be read from mount
RUN chown -R node:node /root

# Global npm tools for development (install as root, one by one for reliability)
# Set npm timeout and retry settings for network reliability
RUN npm config set fetch-timeout 300000 && \
    npm config set fetch-retry-mintimeout 10000 && \
    npm config set fetch-retry-maxtimeout 60000

# Install global packages one by one (continue on failure for robustness)
RUN npm install -g pnpm || echo "pnpm install failed, will install later"
RUN npm install -g yarn || echo "yarn install failed, will install later"  
RUN npm install -g tsx || echo "tsx install failed, will install later"
RUN npm install -g ts-node || echo "ts-node install failed, will install later"
RUN npm install -g nodemon || echo "nodemon install failed, will install later"

# Switch to node user
USER node

# Set working directory
WORKDIR /workspace

# Create .local/bin for user executables
RUN mkdir -p /home/node/.local/bin

# Set PATH
ENV PATH="/home/node/.local/bin:$PATH"

# Default command
CMD ["/bin/bash"]
