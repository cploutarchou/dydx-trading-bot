# 🚀 Quick Reference - dYdX Trading Bot

## One-Line Commands

```bash
# Development
make dev              # Run with hot-reload
make run              # Run without hot-reload
make build            # Build binary

# Code Quality
make lint             # Check code quality
make lint-fix         # Auto-fix issues
make fmt              # Format code
make vet              # Run go vet
make verify           # Full verification (fmt+vet+lint+test)

# Testing
make test             # Run tests
make test-coverage    # Tests + HTML coverage report
make bench            # Run benchmarks

# Security
make security         # Run security scan

# Database
make migrate-up       # Apply migrations
make migrate-down     # Rollback migration
make migrate-create NAME=migration_name  # Create new migration

# Docker
make docker-build     # Build Docker image
docker-compose up -d  # Run full stack

# Cleanup
make clean            # Remove build artifacts

# Help
make help             # Show all commands
```

## File Structure

```
.
├── .golangci.yml           # Linting configuration (30+ linters)
├── .air.toml               # Hot reload configuration
├── Makefile                # All automation commands
├── Dockerfile              # Production Docker image
├── docker-compose.yml      # Full stack (Go+Postgres+Redis)
├── DEVELOPMENT.md          # Complete dev guide
├── SETUP_COMPLETE.md       # Setup summary
│
├── .vscode/
│   ├── launch.json         # Debug configurations
│   └── settings.json       # Editor settings
│
├── cmd/server/main.go      # Application entry point
│
├── internal/
│   ├── auth/               # JWT authentication
│   ├── db/                 # Database layer
│   ├── handlers/           # HTTP handlers
│   ├── middleware/         # HTTP middleware
│   │   ├── auth_middleware.go      # Auth (header/cookie/query)
│   │   ├── header_logging.go       # Request header logging
│   │   ├── rate_limit.go           # Rate limiting
│   │   └── ...
│   ├── models/             # Data models
│   ├── repository/         # Data access
│   ├── routes/             # Route registration
│   └── services/           # Business logic
│
└── migrations/             # Database migrations
```

## Debug Endpoints (Development)

```bash
# Echo request headers (see what client sends)
curl http://localhost:8888/api/v1/debug/headers

# Test auth (requires valid token)
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8888/api/v1/debug/whoami
```

## Authentication Methods

The server accepts tokens via:
1. **Authorization header** (preferred): `Authorization: Bearer <token>`
2. **Cookie**: `access_token=<token>`  
3. **Query param** (debug only): `?access_token=<token>`

## API Endpoints

```bash
# Health check
GET /health

# Authentication
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh

# User
GET /api/v1/users/me              # Requires auth

# Keys
POST /api/v1/keys/create          # Requires auth
GET  /api/v1/keys/list            # Requires auth
GET  /api/v1/keys/:network        # Requires auth
DELETE /api/v1/keys/:network      # Requires auth

# Backtests
GET /api/v1/backtests/:run_id/candles
GET /api/v1/backtests/:run_id/positions
GET /api/v1/backtests/:run_id/trades
```

## Example: Register → Login → Access Protected Route

```bash
# 1. Register
curl -X POST http://localhost:8888/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"passw0rd"}'

# 2. Login (get token)
TOKEN=$(curl -s -X POST http://localhost:8888/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"passw0rd"}' | jq -r '.access_token')

# 3. Call protected endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/users/me
```

## Logging

The server logs:
- Request headers (masked Authorization/Cookie)
- Auth middleware activity (token source: header/cookie/query)
- Token verification errors
- Request/response details

Example log:
```
Headers: GET /api/v1/users/me from ::1 - map[Authorization:[Bearer <masked>] ...]
RequireAuth: Authorization header="Bearer ...", RemoteAddr=[::1]:54131, ClientIP=::1
RequireAuth: using token from cookie 'access_token' (masked)
✅ [GET] /api/v1/users/me - Status: 200 - Duration: 5ms - IP: ::1
```

## Environment Variables

Key variables (.env):
```bash
# Database
DB_TYPE=sqlite3                    # or postgres
DB_NAME=trading_bot
DB_HOST=localhost                  # if postgres
DB_PORT=5432                       # if postgres

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Server
API_PORT=8888
APP_ENV=development                # or production

# Redis (optional)
REDIS_ENABLED=false
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check Authorization header is sent; check logs for token verification errors |
| 429 Too Many Requests | Rate limit hit (localhost is bypassed in dev) |
| 404 Not Found | Check registered routes in startup logs |
| Build errors | `make clean && make deps && make build` |
| Linter not found | `make install-tools` |
| Migration failed | Check SQL syntax; rollback: `make migrate-down` |

## VS Code Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Start debugging | F5 |
| Toggle breakpoint | F9 |
| Step over | F10 |
| Step into | F11 |
| Continue | F5 |
| Format document | Shift+Alt+F |
| Go to definition | F12 |
| Show references | Shift+F12 |

## Git Hooks

Install pre-commit hook:
```bash
cp scripts/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Now every commit will:
1. Check formatting
2. Run go vet
3. Run linter
4. Run tests

## Performance Tips

1. **Use connection pooling** (already configured in db.go)
2. **Enable Redis caching** for frequently-accessed data
3. **Use prepared statements** for repeated queries
4. **Profile with pprof**:
   ```bash
   go test -cpuprofile=cpu.prof -bench=.
   go tool pprof cpu.prof
   ```

## Security Checklist

- ✅ JWT secrets in environment (not hardcoded)
- ✅ HTTPS in production (configure reverse proxy)
- ✅ SQL injection prevention (parameterized queries)
- ✅ Rate limiting enabled
- ✅ CORS configured properly
- ✅ Secrets encrypted (dYdX keys use encryption)
- ✅ Security scanning with gosec
- ✅ Input validation

## Production Deployment

```bash
# Build for production
CGO_ENABLED=1 GOOS=linux go build -o server ./cmd/server

# Or use Docker
docker build -t dydx-bot .
docker run -p 8888:8888 --env-file .env dydx-bot

# Or docker-compose
docker-compose up -d
```

## Useful Links

- [Go Documentation](https://golang.org/doc/)
- [Gin Framework](https://gin-gonic.com/docs/)
- [golangci-lint Linters](https://golangci-lint.run/usage/linters/)
- [DEVELOPMENT.md](./DEVELOPMENT.md) - Full development guide
- [SETUP_COMPLETE.md](./SETUP_COMPLETE.md) - Setup summary

---

**Need help?** Check `DEVELOPMENT.md` or run `make help`

