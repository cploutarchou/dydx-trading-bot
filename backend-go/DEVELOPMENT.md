# dYdX Trading Bot - Development Guide

## 🚀 Quick Start

### Prerequisites
- Go 1.23 or higher
- Make (for using Makefile commands)
- Docker & Docker Compose (optional)

### Installation

1. **Install development tools:**
```bash
make install-tools
```

This installs:
- `golangci-lint` - Fast Go linters runner
- `air` - Live reload for Go apps
- `migrate` - Database migration tool
- `mockgen` - Mock generator for testing

2. **Install dependencies:**
```bash
make deps
```

3. **Run database migrations:**
```bash
make migrate-up
```

### Running the Application

**Development mode (with hot reload):**
```bash
make dev
```

**Standard run:**
```bash
make run
```

**Build and run binary:**
```bash
make build
./bin/dydx-bot
```

## 📋 Available Make Commands

Run `make help` to see all available commands:

```bash
make help
```

### Common Commands

| Command | Description |
|---------|-------------|
| `make build` | Build the application binary |
| `make run` | Run the application |
| `make dev` | Run with hot-reload (requires air) |
| `make test` | Run all tests |
| `make test-coverage` | Run tests and generate coverage report |
| `make lint` | Run golangci-lint |
| `make lint-fix` | Run linter and auto-fix issues |
| `make fmt` | Format code with gofmt |
| `make vet` | Run go vet |
| `make check` | Quick check (fmt + vet + build) |
| `make verify` | Full verification (fmt + vet + lint + test) |
| `make security` | Run security checks with gosec |
| `make clean` | Clean build artifacts |

## 🔍 Linting & Code Quality

### Running Linters

**Check for issues:**
```bash
make lint
```

**Auto-fix issues:**
```bash
make lint-fix
```

**Configuration:**
Linting configuration is in `.golangci.yml`. Adjust settings there to customize linter behavior.

### Enabled Linters

- **errcheck** - Check for unchecked errors
- **gosimple** - Simplify code
- **govet** - Reports suspicious constructs
- **staticcheck** - Advanced static analysis
- **gofmt** - Code formatting
- **goimports** - Import organization
- **goconst** - Find repeated strings
- **gocyclo** - Cyclomatic complexity
- **revive** - Fast, configurable linter
- **gosec** - Security issues
- And many more...

## 🧪 Testing

### Run Tests

**All tests:**
```bash
make test
```

**With coverage:**
```bash
make test-coverage
```

**Benchmarks:**
```bash
make bench
```

**Specific package:**
```bash
go test -v ./internal/auth/...
```

**Specific test:**
```bash
go test -v -run TestFunctionName ./internal/auth
```

### Test Environment

Tests use `.env.test` for configuration. Modify it as needed for your test environment.

## 🐛 Debugging

### VS Code

The project includes VS Code debug configurations in `.vscode/launch.json`:

1. **Launch Server** - Debug the main application
2. **Attach to Process** - Attach to running process
3. **Debug Test** - Debug specific tests
4. **Debug Package Tests** - Debug all tests in current package
5. **Debug Current File** - Debug current file

**To debug:**
1. Open VS Code
2. Set breakpoints
3. Press F5 or go to Run & Debug panel
4. Select configuration and start debugging

### Delve (Command Line)

```bash
# Install delve
go install github.com/go-delve/delve/cmd/dlv@latest

# Debug application
dlv debug ./cmd/server

# Debug with arguments
dlv debug ./cmd/server -- --config=config.json

# Debug test
dlv test ./internal/auth
```

## 📊 Code Coverage

**Generate coverage report:**
```bash
make test-coverage
```

This creates:
- `coverage.out` - Coverage profile
- `coverage.html` - HTML coverage report (open in browser)

**View coverage in terminal:**
```bash
go test -cover ./...
```

**Detailed coverage per function:**
```bash
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out
```

## 🔐 Security Scanning

**Run security checks:**
```bash
make security
```

This runs `gosec` and generates `gosec-report.json`.

**Fix common security issues:**
- Always validate input
- Use parameterized queries
- Don't log sensitive data
- Use HTTPS in production
- Rotate secrets regularly

## 🗄️ Database Migrations

### Create Migration

```bash
make migrate-create NAME=add_users_table
```

This creates two files:
- `migrations/NNNNNN_add_users_table.up.sql`
- `migrations/NNNNNN_add_users_table.down.sql`

### Run Migrations

**Up (apply):**
```bash
make migrate-up
```

**Down (rollback one):**
```bash
make migrate-down
```

## 🐳 Docker

### Build Image

```bash
make docker-build
```

### Run with Docker Compose

```bash
docker-compose up -d
```

**Services:**
- Backend API (port 8888)
- PostgreSQL (port 5432)
- Redis (port 6379)

**Stop services:**
```bash
docker-compose down
```

**View logs:**
```bash
docker-compose logs -f backend
```

## 📝 Code Style Guide

### General Guidelines

1. **Use gofmt/goimports** - Always format code
2. **Error handling** - Always check errors
3. **Naming conventions:**
   - Packages: lowercase, single word
   - Functions/methods: camelCase (exported: PascalCase)
   - Constants: PascalCase or UPPER_CASE
4. **Comments:**
   - Exported functions must have doc comments
   - Start with function name: `// FunctionName does...`
5. **Keep functions small** - Aim for <50 lines
6. **Avoid naked returns** - Be explicit

### Example

```go
// GetUserByID retrieves a user by their ID.
// Returns an error if the user is not found or database error occurs.
func GetUserByID(ctx context.Context, db *sql.DB, userID int) (*User, error) {
	if userID <= 0 {
		return nil, fmt.Errorf("invalid user ID: %d", userID)
	}

	user := &User{}
	err := db.QueryRowContext(ctx, "SELECT * FROM users WHERE id = $1", userID).
		Scan(&user.ID, &user.Username, &user.Email)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("user not found: %w", err)
		}
		return nil, fmt.Errorf("database error: %w", err)
	}

	return user, nil
}
```

## 🔧 Hot Reload (Development)

Uses `air` for automatic reloading during development.

**Configuration:** `.air.toml`

**Run:**
```bash
make dev
```

Air will watch for file changes and automatically rebuild and restart the application.

## 📚 Additional Resources

- [Effective Go](https://golang.org/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
- [golangci-lint Documentation](https://golangci-lint.run/)
- [Standard Go Project Layout](https://github.com/golang-standards/project-layout)

## 🛠️ Troubleshooting

### Linter Issues

**"golangci-lint not found":**
```bash
make install-tools
```

**Too many linter errors:**
```bash
# Fix auto-fixable issues
make lint-fix

# Or disable specific linters in .golangci.yml
```

### Build Issues

**Missing dependencies:**
```bash
make deps
make tidy
```

**Cache issues:**
```bash
make clean
go clean -cache -modcache -testcache
```

### Migration Issues

**"migrate command not found":**
```bash
make install-tools
```

**Migration failed:**
```bash
# Check migration SQL syntax
# Manually rollback if needed
make migrate-down
```

## 📞 Getting Help

If you encounter issues:
1. Check this documentation
2. Run `make help` for available commands
3. Check logs for error details
4. Review `.golangci.yml` for linter configuration

