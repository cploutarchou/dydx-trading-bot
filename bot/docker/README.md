# 🐳 dYdX Trading Bot - Docker Setup

Complete Docker containerization for the dYdX Trading Bot with JWT authentication, featuring production-ready deployment with PostgreSQL, Redis, Nginx, and comprehensive monitoring.

## 📋 Quick Start

```bash
# 1. Setup development environment
make setup

# 2. Quick start (creates .env, SSL certs, builds images, and starts services)
make quick-start

# 3. Initialize authentication
make init-auth

# 4. Access the application
open https://localhost/docs
```

**Default Admin Credentials:**

- Username: `admin`
- Password: `admin123`

## 📂 Directory Structure

```
docker/
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # Complete service orchestration
├── .env.docker               # Environment template
├── .env                      # Your configuration (created from template)
├── setup-dev.sh              # Development setup script
├── nginx/
│   └── nginx.conf            # Production Nginx configuration
├── ssl/
│   ├── generate-ssl.sh       # SSL certificate generator
│   ├── cert.pem              # SSL certificate (generated)
│   └── private.key           # SSL private key (generated)
├── sql/
│   └── init.sql              # PostgreSQL initialization
└── monitoring/
    └── prometheus.yml        # Monitoring configuration
```

## 🚀 Available Make Commands

Run `make help` to see all available commands:

### 📦 Setup Commands

- `make setup` - Setup development environment (run first)
- `make init-env` - Initialize .env from template
- `make init-ssl` - Generate SSL certificates
- `make init-auth` - Initialize authentication database

### 🏗️ Build Commands

- `make build` - Build Docker images
- `make build-dev` - Build development images
- `make build-prod` - Build production images

### 🚀 Development Commands

- `make dev` - Start development environment (foreground)
- `make dev-detached` - Start development environment (background)
- `make test` - Run tests
- `make test-auth` - Test authentication system

### 🏭 Production Commands

- `make prod` - Start production environment
- `make deploy` - Build and deploy production

### 🔧 Management Commands

- `make start` - Start services
- `make stop` - Stop services
- `make restart` - Restart services
- `make status` - Show container status
- `make logs` - Show all logs
- `make logs-api` - Show API logs only

### 🗄️ Database Commands

- `make db-shell` - Connect to database
- `make db-backup` - Create database backup
- `make db-reset` - Reset database (destructive)

### 🔍 Debugging Commands

- `make shell` - Open shell in API container
- `make health` - Check service health
- `make info` - Show project information

## ⚙️ Configuration

### Environment Variables

Copy and edit the environment file:

```bash
cp docker/.env.docker docker/.env
```

**Key Configuration Options:**

```bash
# Database
DB_NAME=dydx_trading_bot
DB_USER=botuser
DB_PASSWORD=your_secure_password

# JWT Authentication
SECRET_KEY=your-super-secure-secret-key-32-chars-min
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email (for 2FA and password reset)
EMAIL_PROVIDER=mailgun
MAILGUN_API_KEY=your-mailgun-api-key
MAILGUN_DOMAIN=yourdomain.com

# Trading
DYDX_NETWORK=testnet
```

### SSL Certificates

For development, self-signed certificates are automatically generated:

```bash
make init-ssl
```

For production, replace with Let's Encrypt or commercial certificates:

```bash
# Let's Encrypt example
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/ssl/private.key
```

## 🏗️ Architecture Overview

### Services

1. **bot-api** - FastAPI application with JWT authentication
2. **postgres** - PostgreSQL database for persistent data
3. **redis** - Redis cache for session management
4. **nginx** - Reverse proxy with SSL termination and security headers

### Network Security

- **Rate limiting** on authentication endpoints
- **Security headers** (HSTS, CSP, X-Frame-Options)
- **IP-based connection limits**
- **TLS 1.2+ only** with modern cipher suites

### Resource Management

- **Multi-stage builds** for optimized production images
- **Non-root user** execution for security
- **Resource limits** configured in docker-compose
- **Health checks** for all services

## 📊 Monitoring & Health Checks

### Built-in Health Endpoints

```bash
# API Health
curl https://localhost/health

# Authentication Health
curl https://localhost/auth/health

# Database Health (via container)
make db-shell
\conninfo
```

### Service Status

```bash
# Quick status check
make status

# Detailed health check
make health

# Container resource usage
docker stats $(docker-compose -f docker/docker-compose.yml ps -q)
```

## 🔒 Security Best Practices

### Production Checklist

- [ ] **Change default passwords** in `.env`
- [ ] **Generate secure SECRET_KEY** (32+ characters)
- [ ] **Configure email provider** for password reset
- [ ] **Use valid SSL certificates** (Let's Encrypt/commercial)
- [ ] **Set up firewall rules** (block direct API access)
- [ ] **Enable database backups**
- [ ] **Monitor authentication logs**
- [ ] **Regular security updates**

### Authentication Security

```bash
# Enable 2FA for admin user
curl -X POST "https://localhost/auth/2fa/setup" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Change default password
curl -X POST "https://localhost/auth/change-password" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "admin123", "new_password": "new_secure_password"}'
```

## 💾 Backup & Recovery

### Database Backup

```bash
# Create backup
make db-backup

# List backups
ls -la backups/

# Restore from backup
make db-restore BACKUP_FILE=backups/backup_20251102_120000.sql.gz
```

### Full System Backup

```bash
# Backup application data
docker run --rm -v dydx-trading-bot_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_data_$(date +%Y%m%d).tar.gz -C /data .

# Backup configuration
tar czf backups/config_$(date +%Y%m%d).tar.gz docker/.env docker/ssl/
```

## 🚨 Troubleshooting

### Common Issues

**Port Already in Use:**

```bash
# Check what's using port 8000
lsof -i :8000
# Kill the process and restart
make restart
```

**SSL Certificate Issues:**

```bash
# Regenerate certificates
make init-ssl
# Restart Nginx
docker-compose -f docker/docker-compose.yml restart nginx
```

**Database Connection Issues:**

```bash
# Check database logs
make logs-db
# Reset database if needed
make db-reset
```

**Authentication Issues:**

```bash
# Check API logs
make logs-api
# Test authentication manually
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Debug Mode

For detailed debugging:

```bash
# Start in development mode with logs
make dev

# Open shell in container
make shell

# Check service health
make health
```

## 🔄 Development Workflow

### Local Development

```bash
# 1. Setup (first time only)
make setup

# 2. Start development environment
make dev-detached

# 3. Initialize authentication (first time only)
make init-auth

# 4. Make code changes (hot reload enabled)

# 5. Run tests
make test

# 6. View logs
make logs-api
```

### Code Changes

The development environment includes hot reload. Simply modify your Python files and the API server will automatically restart.

### Testing

```bash
# Run all tests
make test

# Test authentication specifically
make test-auth

# Manual API testing
curl -X GET "http://localhost:8000/docs"
```

## 🌐 Production Deployment

### Basic Production Setup

```bash
# 1. Configure production environment
cp docker/.env.docker docker/.env
# Edit docker/.env with production values

# 2. Generate/install SSL certificates
make init-ssl  # or install Let's Encrypt certs

# 3. Deploy
make deploy

# 4. Initialize authentication
make init-auth

# 5. Verify deployment
make health
```

### Advanced Production Options

For advanced production deployment with monitoring:

```bash
# Start with monitoring stack
docker-compose -f docker/docker-compose.yml --profile monitoring up -d

# Access monitoring
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```

## 📚 API Access

Once deployed, access the API at:

- **API Documentation:** `https://localhost/docs`
- **Health Check:** `https://localhost/health`
- **Authentication:** `https://localhost/auth/login`

### Authentication Flow

```bash
# 1. Login
TOKEN=$(curl -X POST "https://localhost/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  jq -r '.data.access_token')

# 2. Use authenticated endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "https://localhost/api/v1/bots"
```

## 🆘 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review logs: `make logs-api`
3. Check service health: `make health`
4. Review the main documentation in `AUTHENTICATION_GUIDE.md`

---

**🎉 Your dYdX Trading Bot is now fully containerized and ready for production deployment!**
