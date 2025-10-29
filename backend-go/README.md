# dYdX Trading Bot - Go Backend

A high-performance REST API backend written in Go for managing dYdX trading credentials and accessing backtest data.

## ⭐ Features

✅ **Secure Key Management**
- Encrypted storage of dYdX mnemonic phrases
- Support for testnet and mainnet keys
- Per-user key isolation

✅ **JWT Authentication**
- Secure token-based authentication
- Cookie-based authentication for browsers
- Configurable token expiration
- Refresh token support

✅ **Database Support**
- PostgreSQL for production
- SQLite for development/testing
- Automatic schema migrations

✅ **Backtest Data API**
- Historical price candles
- Position data with P&L metrics
- Individual trade records
- Pagination support

✅ **Production Ready**
- CORS support with credential handling
- Error handling middleware
- Rate limiting (with localhost bypass for dev)
- Logging and monitoring
- Health check endpoint
- Security scanning

✅ **Developer Experience**
- Hot reload with Air
- Comprehensive linting (30+ linters)
- VS Code debug configurations
- Docker support
- Automated testing
- Pre-commit hooks
- CI/CD ready

## 🚀 Quick Start

```bash
# Install development tools (linters, hot reload, etc.)
make install-tools

# Run with hot reload
make dev

# Or run normally
make run
```

That's it! The server will start on http://localhost:8888

## 📋 Prerequisites

- **Go 1.23.0 or higher**
- PostgreSQL 12+ (for production) OR SQLite (for development)
- Redis (optional, for caching)
- Make (for using Makefile commands)

## 📦 Installation

### 1. Navigate to project

```bash
cd /Users/chris/workspace/dydx-trading-bot/backend-go
```

### 2. Install dependencies

```bash
make deps
# or
go mod download
go mod tidy
```

### 3. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database setup
DB_TYPE=sqlite3           # or postgresql
DB_NAME=trading_bot

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEY=your-encryption-key-change-in-production

# dYdX Configuration
DYDX_TESTNET_ADDRESS=dydx1...
DYDX_TESTNET_SECRET=your_mnemonic_phrase

# API Port
API_PORT=8080
```

### 4. Run database migrations

Migrations run automatically on startup, but you can verify with:

```bash
# Using golang-migrate CLI
migrate -path migrations -database "sqlite3://trading_bot.db" up
```

### 5. Start the server

```bash
go run ./cmd/server/main.go
```

Or build and run:

```bash
go build -o trading-bot ./cmd/server
./trading-bot
```

The API will be available at `http://localhost:8080`

## Project Structure

```
backend-go/
├── cmd/
│   └── server/
│       └── main.go              # Application entry point
├── config/
│   └── config.go                # Configuration management
├── internal/
│   ├── auth/
│   │   └── jwt.go               # JWT token management
│   ├── db/
│   │   └── db.go                # Database connection
│   ├── handlers/
│   │   ├── backtest_handler.go  # Backtest endpoints
│   │   └── key_handler.go       # Key management endpoints
│   ├── middleware/
│   │   ├── auth_middleware.go   # JWT authentication
│   │   ├── error_middleware.go  # Error handling
│   │   └── middleware.go        # CORS, logging
│   ├── models/
│   │   └── models.go            # Data models
│   ├── repository/
│   │   ├── key_repo.go          # Key database operations
│   │   └── user_repo.go         # User database operations
│   ├── routes/
│   │   ├── backtest_routes.go   # Backtest routes
│   │   └── key_routes.go        # Key management routes
│   └── services/
│       └── key_service.go       # Key business logic
├── migrations/                  # Database migrations
├── .env.example                 # Example environment file
├── API_DOCUMENTATION.md         # Complete API reference
├── go.mod                       # Go module definition
└── go.sum                       # Dependency checksums
```

## Configuration

### Database Configuration

#### SQLite (Development)

```env
DB_TYPE=sqlite3
DB_NAME=trading_bot
```

Creates `trading_bot.db` in the project root.

#### PostgreSQL (Production)

```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dydx_trading_bot
DB_USER=postgres
DB_PASSWORD=your_password
SSL_MODE=require
```

### JWT Configuration

```env
JWT_SECRET_KEY=your-secret-key-minimum-32-characters
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Key Encryption

```env
# Used for encrypting stored dYdX secret phrases
ENCRYPTION_KEY=your-encryption-key-minimum-32-characters
```

### Redis (Optional)

```env
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## API Endpoints

### Health Check

```
GET /health
```

### Authentication

```
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

### Key Management

```
POST /api/v1/keys/create           # Create/update key
GET /api/v1/keys/list              # List user's keys
GET /api/v1/keys/{network}         # Get key info
GET /api/v1/keys/{network}/secret  # Get key with secret
DELETE /api/v1/keys/{network}      # Delete key
```

### Backtest Data

```
GET /api/v1/backtests/{run_id}/candles     # Historical candles
GET /api/v1/backtests/{run_id}/positions   # Trading positions
GET /api/v1/backtests/{run_id}/trades      # Individual trades
```

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for full endpoint details.

## Development

### Running Tests

```bash
go test ./...
go test -v ./...
go test -cover ./...
```

### Building Docker Image

```bash
docker build -t dydx-trading-bot-backend .
docker run -p 8080:8080 --env-file .env dydx-trading-bot-backend
```

### Code Format

```bash
go fmt ./...
goimports -w ./...
```

### Linting

```bash
go vet ./...
golangci-lint run ./...
```

## Database Schema

### dydx_keys Table

Stores encrypted dYdX credentials:

```sql
CREATE TABLE dydx_keys (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    network VARCHAR(20) NOT NULL,
    chain_address VARCHAR(255) NOT NULL,
    encrypted_secret TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, network)
);
```

### Migration System

Using `golang-migrate`:

```bash
# Create new migration
migrate create -ext sql -dir migrations -seq create_table_name

# Run migrations
migrate -path migrations -database "postgres://..." up

# Rollback
migrate -path migrations -database "postgres://..." down
```

## Security Best Practices

### Environment Variables

Never commit `.env` to version control:

```bash
echo ".env" >> .gitignore
echo "*.db" >> .gitignore
echo "dydx_bot.db" >> .gitignore
```

### Encryption

- All dYdX secret phrases are encrypted using AES-256-GCM
- Encryption key must be at least 32 characters
- Rotate encryption keys regularly

### Token Management

- Store JWT tokens securely on the client
- Use HTTPS in production
- Set appropriate token expiration times
- Implement token rotation

### Database

- Use strong PostgreSQL passwords
- Enable SSL/TLS connections
- Regular backups
- Principle of least privilege for database users

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
API_PORT=8081 go run ./cmd/server/main.go
```

### Database Connection Error

```bash
# Check PostgreSQL is running
psql -h localhost -U postgres -d postgres

# Verify credentials in .env
# Check DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
```

### JWT Token Errors

```
Token expired: Refresh using the refresh token endpoint
Invalid token: Check JWT_SECRET_KEY matches
```

### Migration Errors

```bash
# Check migration files exist
ls -la migrations/

# View migration status
migrate -path migrations -database "..." version

# Force reset (development only!)
migrate -path migrations -database "..." drop
```

## Performance Optimization

### Connection Pooling

Configured in `.env`:

```env
DB_MAX_CONNECTIONS=10
DB_POOL_SIZE=5
REDIS_MAX_CONNECTIONS=10
```

Adjust based on your load testing results.

### Caching

Enable Redis caching:

```env
REDIS_ENABLED=true
REDIS_CACHE_TTL=86400  # 24 hours
```

### Indexing

Ensure database indexes exist:

```sql
CREATE INDEX idx_dydx_keys_user_id ON dydx_keys(user_id);
CREATE INDEX idx_dydx_keys_user_network ON dydx_keys(user_id, network);
CREATE INDEX idx_backtest_runs_user_id ON backtest_runs(user_id);
```

## Deployment

### Docker

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY . .
RUN go mod download
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o trading-bot ./cmd/server

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/trading-bot .
COPY --from=builder /app/migrations ./migrations
EXPOSE 8080
CMD ["./trading-bot"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-bot-backend
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: backend
        image: trading-bot-backend:latest
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: db-config
              key: host
```

### Environment-Specific Configs

Create config files for each environment:

```
.env.development
.env.staging
.env.production
```

## Monitoring and Logging

### Health Check

```bash
curl http://localhost:8080/health
```

### Structured Logging

The application logs to stdout. Integrate with your logging system:

```bash
# Send logs to file
./trading-bot 2>&1 | tee app.log

# Forward to ELK/Datadog/etc
./trading-bot | logger -t trading-bot
```

### Metrics

Consider adding Prometheus metrics:

```go
import "github.com/prometheus/client_golang/prometheus"
```

## Contributing

1. Create a feature branch
2. Make changes following Go best practices
3. Run tests and linting
4. Submit a pull request

## License

[Your License Here]

## Support

For issues, questions, or contributions, please:

1. Check the API documentation
2. Review error logs
3. Open an issue on the repository

## Related Documentation

- [API Documentation](./API_DOCUMENTATION.md)
- [Go Best Practices](https://golang.org/doc/effective_go)
- [Gin Web Framework](https://github.com/gin-gonic/gin)
- [dYdX Protocol](https://dydx.community/)

