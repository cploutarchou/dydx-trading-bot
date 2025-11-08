# dYdX Trading Bot Backend - AI Coding Guide

## Architecture Overview

This is a **layered Go REST API** for managing dYdX trading credentials and backtest data. The architecture follows **dependency injection** and **repository patterns**:

- **`cmd/server/main.go`** - Application entry with middleware chain setup
- **`config/config.go`** - Centralized config loading from env vars with defaults
- **`internal/db/db.go`** - Database abstraction with connection pooling, retries, and auto-migrations
- **Repository Layer** (`internal/repository/`) - Database operations with prepared statements
- **Service Layer** (`internal/services/`) - Business logic including AES-256-GCM encryption
- **Handler Layer** (`internal/handlers/`) - HTTP request/response processing
- **Routes** (`internal/routes/`) - Route registration with middleware injection

## Key Development Patterns

### Database Operations

- **Dual database support**: SQLite (dev) vs PostgreSQL (prod) using `DB_TYPE` env var
- **Auto-migrations** run on startup via `golang-migrate` with recovery for dirty state
- **Connection management**: Use `database.Query()`, `database.Exec()` methods, not raw `database.DB`
- **Migration naming**: `000XXX_description.{up,down}.sql` with sequential numbering

### Security & Encryption

- **JWT middleware chain**: `RequireAuth()` → extracts `user_id`, `username`, `email`, `is_admin` into context
- **Key encryption**: AES-256-GCM in `services/key_service.go` using `ENCRYPTION_KEY` env var
- **Environment secrets**: Use `.env` file (never committed), loaded via `godotenv.Load()`

### Request Flow

```
gin.Router → CORSMiddleware → AuthMiddleware → RateLimitMiddleware → Handler → Service → Repository → DB
```

## Development Commands

### Essential Workflow

```bash
# Install dev tools (required first-time setup)
make install-tools

# Development with hot-reload
make dev

# Full verification pipeline
make verify  # fmt + vet + lint + test

# Database operations
make migrate-up
make migrate-create NAME=your_migration_name
```

### Environment Setup

- Copy `.env.example` → `.env` and configure database settings
- **SQLite**: Set `DB_TYPE=sqlite3` for local development
- **PostgreSQL**: Use Docker Compose with `docker-compose up -d postgres redis`

## Project-Specific Conventions

### Error Handling

- Services return `(result, error)` - handlers convert to JSON responses
- Database errors wrapped with context: `fmt.Errorf("failed to create key: %w", err)`
- Use structured logging: `log.Printf("✅ Database connected successfully (%s): %s", driver, sanitizedDSN)`

### Route Structure

All routes follow `/api/v1/{resource}/{action}` pattern:

- **Protected routes**: Wrapped in `middleware.RequireAuth()`
- **Resource grouping**: Keys, backtests, strategies use separate route files
- **Parameter extraction**: `c.Param("network")`, user context via `c.Get("user_id")`

### Model Definitions

- **Shared models** in `internal/models/models.go` with both `db` and `json` tags
- **Time handling**: Use `time.Time` with RFC3339 formatting in JSON responses
- **Nullable fields**: Use `*int`, `*float64`, `sql.NullString` for optional database columns

### Configuration Management

- **Centralized config** in `config/config.go` with env var defaults
- **Database DSN generation** handles both SQLite paths and PostgreSQL connection strings
- **Migration path switching** based on database type (`migrations/sqlite` vs `migrations/postgres`)

## Integration Points

### dYdX Integration

- **Network switching**: `testnet` vs `mainnet` keys stored per user
- **Encrypted storage**: Mnemonic phrases encrypted before database storage
- **Chain addresses**: Public keys stored alongside encrypted private keys

### Authentication Flow

- **Login** → JWT access token (30min) + refresh token (7 days)
- **Token validation** extracts user claims into Gin context for downstream handlers
- **CORS configuration** supports credentials for browser-based clients

### Backtest Data API

- **Historical data** served from pre-populated database tables
- **Pagination support** via query parameters for large datasets
- **Multi-format results**: Candles, positions, trades, and aggregated metrics

## Critical Files to Understand

- **`cmd/server/main.go`** - Middleware order and route registration
- **`internal/db/db.go`** - Database connection lifecycle and migration handling
- **`internal/middleware/auth_middleware.go`** - JWT validation and user context injection
- **`config/config.go`** - Environment variable mapping and defaults
- **Migration files** - Schema evolution and data model relationships

## Communication Guidelines

- **No markdown summaries**: When completing tasks, provide brief verbal summaries in chat rather than creating separate markdown files
- **Direct feedback**: Communicate progress and results directly in conversation
- **Focus on implementation**: Prioritize code changes and actual work over documentation of completed tasks
