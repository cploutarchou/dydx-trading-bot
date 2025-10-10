# Docker Setup Guide

This guide covers containerized deployment of the dYdX Trading Bot using Docker and Docker Compose.

## 🐳 Overview

The dYdX Trading Bot provides a comprehensive Docker setup with:
- **Multi-stage Dockerfile** for optimized production images
- **Docker Compose** for orchestrated deployments
- **Development containers** for interactive development
- **Integrated logging** with Grafana Loki support
- **Security hardening** with non-root user execution

## 📋 Prerequisites

### System Requirements
- Docker Engine 20.10+ 
- Docker Compose v2.0+
- 2GB+ available RAM
- 1GB+ available disk space

### Installation

#### Ubuntu/Debian
```bash
# Install Docker Engine
sudo apt update
sudo apt install docker.io docker-compose-v2

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

#### macOS
```bash
# Install via Homebrew
brew install docker docker-compose

# Or download Docker Desktop
# https://www.docker.com/products/docker-desktop
```

#### Windows
```bash
# Install Docker Desktop
# https://www.docker.com/products/docker-desktop

# Enable WSL2 backend (recommended)
```

## 🏗️ Dockerfile Architecture

### Multi-Stage Build

The Dockerfile uses a multi-stage approach for optimized images:

```dockerfile
# Stage 1: Base image with system dependencies
FROM python:3.12-slim as base
# System packages, user creation, directory setup

# Stage 2: Development image with dev tools  
FROM base as development
# Additional dev packages, testing tools

# Stage 3: Production image (optimized)
FROM base as production  
# Only runtime dependencies, security hardening

# Stage 4: Testing image with test dependencies
FROM base as testing
# Test frameworks, additional development tools
```

### Image Targets

| Target | Purpose | Size | Use Case |
|--------|---------|------|----------|
| `base` | Foundation | ~200MB | Base layer |
| `development` | Dev environment | ~300MB | Local development |
| `production` | Optimized runtime | ~250MB | Production deployment |
| `testing` | CI/CD testing | ~320MB | Automated testing |

### Build Examples

```bash
# Production image (default)
docker build -t dydx-trading-bot .

# Development image
docker build --target development -t dydx-trading-bot:dev .

# Testing image
docker build --target testing -t dydx-trading-bot:test .
```

## ⚙️ Makefile Commands

The project includes comprehensive Makefile commands for Docker operations:

### Basic Operations
```bash
# Build production image
make docker-build

# Run bot container
make docker-run

# Stop running container
make docker-stop

# View container logs
make docker-logs

# Check container status
make docker-status
```

### Development Operations
```bash
# Build development image
make docker-build-dev

# Interactive development container
make docker-dev

# Shell into running container
make docker-shell

# Run tests in container
make docker-test
```

### Docker Compose Operations
```bash
# Start with Docker Compose (recommended)
make docker-up

# Start development environment
make docker-up-dev

# Start with logging stack (Loki + Grafana)
make docker-up-logging

# Stop all services
make docker-down

# View compose logs
make docker-compose-logs
```

### Cleanup Operations
```bash
# Remove container only
make docker-clean-container

# Remove image only  
make docker-clean-image

# Full cleanup (containers, images, volumes)
make docker-clean
```

## 🐙 Docker Compose Configuration

### Service Definitions

#### Production Configuration
```yaml
# docker-compose.yml
version: '3.8'

services:
  dydx-bot:
    build:
      context: .
      target: production
    container_name: dydx-trading-bot
    restart: unless-stopped
    volumes:
      - ./app/config.yaml:/app/config.yaml:ro
      - bot-state:/app/state
    networks:
      - dydx-network
    environment:
      - PYTHONPATH=/app
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import sys; sys.exit(0)'"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
```

#### Development Configuration
```yaml
# docker-compose.override.yml (automatically loaded)
version: '3.8'

services:
  dydx-bot:
    build:
      target: development
    volumes:
      - ./app:/app
      - ./tests:/tests
      - ./scripts:/scripts
    environment:
      - DEBUG=1
    command: ["python", "main.py"]
```

### Volume Management

| Volume | Purpose | Mount Point | Persistence |
|--------|---------|-------------|-------------|
| `config.yaml` | Configuration | `/app/config.yaml` | Host file |
| `bot-state` | Trading state | `/app/state` | Named volume |
| `app/` | Source code (dev) | `/app` | Host directory |
| `logs/` | Log files | `/app/logs` | Host directory |

### Network Configuration

```yaml
networks:
  dydx-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## 🚀 Deployment Scenarios

### 1. Quick Start Deployment

```bash
# Clone repository
git clone <repository-url>
cd dydx-trading-bot

# Create configuration
make config
# Edit app/config.yaml with your settings

# Deploy with Docker Compose
make docker-up
```

### 2. Development Deployment

```bash
# Start development environment
make docker-up-dev

# Access development container
make docker-shell

# Run tests inside container
pytest tests/

# Monitor logs
make docker-logs
```

### 3. Production Deployment

```bash
# Build optimized production image
make docker-build

# Deploy with resource limits
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Monitor deployment
make docker-status
make docker-logs
```

### 4. CI/CD Deployment

```bash
# Build and test
make docker-build
make docker-test

# Push to registry (if configured)
docker tag dydx-trading-bot:latest your-registry.com/dydx-trading-bot:latest
docker push your-registry.com/dydx-trading-bot:latest

# Deploy to production
docker-compose pull
docker-compose up -d
```

## 📊 Monitoring & Logging Stack

### Integrated Logging with Loki

The bot includes optional Grafana Loki integration:

```yaml
# docker-compose.logging.yml
services:
  loki:
    image: grafana/loki:latest
    container_name: loki
    ports:
      - "3100:3100"
    volumes:
      - loki-data:/tmp/loki

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
      - ./config/grafana:/etc/grafana/provisioning
```

### Enable Logging Stack

```bash
# Start bot with logging infrastructure
make docker-up-logging

# Access Grafana dashboard
open http://localhost:3000
# Login: admin/admin
```

### Log Configuration

Update `app/config.yaml` for Loki integration:

```yaml
logging:
  level: "INFO"
  loki:
    enabled: true
    url: "http://loki:3100"
    labels:
      app: "dydx-trading-bot"
      environment: "production"
```

## 🔒 Security Configuration

### Non-Root User

The container runs as non-root user for security:

```dockerfile
# Create non-root user
RUN groupadd -r dydxbot && useradd -r -g dydxbot -d /app -s /sbin/nologin dydxbot

# Set ownership and switch user
RUN chown -R dydxbot:dydxbot /app
USER dydxbot
```

### Secret Management

#### 1. Environment Variables
```bash
# Set via environment
export DYDX_ADDRESS="your-address"
export DYDX_SECRET="your-mnemonic"
export TELEGRAM_TOKEN="your-token"

# Run with environment
docker run --env DYDX_ADDRESS --env DYDX_SECRET dydx-trading-bot
```

#### 2. Docker Secrets
```yaml
# docker-compose.yml
services:
  dydx-bot:
    secrets:
      - dydx_config
    volumes:
      - /run/secrets/dydx_config:/app/config.yaml:ro

secrets:
  dydx_config:
    file: ./secrets/config.yaml
```

#### 3. External Secret Managers
```bash
# Using Docker secrets from external source
echo "your-secret" | docker secret create dydx_secret -
```

### Network Security

```yaml
# Restrict network access
networks:
  dydx-network:
    internal: true  # No external access
    
# Only expose necessary ports
ports:
  - "127.0.0.1:8080:8080"  # Bind to localhost only
```

## 🏥 Health Checks & Monitoring

### Container Health Checks

```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c 'import sys; sys.exit(0)'"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Monitoring Commands

```bash
# Check container health
docker inspect dydx-trading-bot --format='{{.State.Health.Status}}'

# View resource usage
docker stats dydx-trading-bot

# Monitor logs in real-time
docker logs -f dydx-trading-bot

# Check container processes
docker exec dydx-trading-bot ps aux
```

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.5'
    reservations:
      memory: 512M
      cpus: '0.25'
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs for startup errors
docker logs dydx-trading-bot

# Common causes:
# - Missing config.yaml file
# - Invalid configuration syntax
# - Network connectivity issues
# - Insufficient resources
```

#### 2. Configuration Problems
```bash
# Validate configuration file
docker run --rm -v ./app/config.yaml:/app/config.yaml dydx-trading-bot \
  python -c "from config import config; print('Config valid:', config() is not None)"

# Check file permissions
ls -la app/config.yaml
# Should be readable by container user
```

#### 3. Network Connectivity
```bash
# Test dYdX connectivity from container
docker exec dydx-trading-bot \
  python -c "import asyncio; from func_connections import connect_dydx; asyncio.run(connect_dydx())"

# Check DNS resolution
docker exec dydx-trading-bot nslookup indexer.dydx.trade
```

#### 4. Memory/Performance Issues
```bash
# Monitor resource usage
docker stats dydx-trading-bot

# Check for memory leaks
docker exec dydx-trading-bot ps aux --sort=-%mem

# Restart if needed
docker restart dydx-trading-bot
```

### Debug Mode

```bash
# Run in debug mode with interactive access
docker run -it --rm \
  -v ./app/config.yaml:/app/config.yaml:ro \
  -e DEBUG=1 \
  dydx-trading-bot:dev bash

# Inside container, run components individually
python -c "from config import config; print(config())"
python -c "import asyncio; from func_connections import connect_dydx; asyncio.run(connect_dydx())"
```

### Log Analysis

```bash
# Extract logs for analysis
docker logs dydx-trading-bot > bot-logs.txt

# Search for specific errors
docker logs dydx-trading-bot 2>&1 | grep -i error

# Follow logs with timestamps
docker logs -f -t dydx-trading-bot
```

## 📈 Performance Optimization

### Image Optimization

```dockerfile
# Multi-stage build reduces final image size
FROM python:3.12-slim as base
# Install only required system packages

FROM base as production
# Copy only necessary files
COPY app/ /app/
# Don't include development files, tests, docs
```

### Runtime Optimization

```yaml
# Optimize container resources
deploy:
  resources:
    limits:
      memory: 512M      # Adjust based on usage
      cpus: '0.25'      # Bot is not CPU intensive
```

### Volume Performance

```bash
# Use named volumes for better performance
docker volume create bot-state

# Avoid bind mounts for frequently accessed data
# Use volumes instead of bind mounts for state files
```

## 🔄 Updates & Maintenance

### Rolling Updates

```bash
# Build new image
make docker-build

# Rolling update with zero downtime
docker-compose pull
docker-compose up -d --force-recreate
```

### Backup State

```bash
# Backup trading state
docker run --rm \
  -v bot-state:/source:ro \
  -v ./backups:/backup \
  alpine tar czf /backup/bot-state-$(date +%Y%m%d).tar.gz -C /source .

# Restore from backup
docker run --rm \
  -v bot-state:/target \
  -v ./backups:/backup \
  alpine tar xzf /backup/bot-state-20241009.tar.gz -C /target
```

### Automated Updates

```bash
# Create update script
#!/bin/bash
set -e

echo "Starting dYdX bot update..."

# Pull latest code
git pull origin main

# Rebuild image  
make docker-build

# Stop current container
make docker-stop

# Start updated container
make docker-run

echo "Update completed successfully"
```

This comprehensive Docker setup provides production-ready containerization with security, monitoring, and maintenance best practices for the dYdX Trading Bot.