package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/mysql"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

var (
	// ErrNilConnection indicates the database connection is nil
	ErrNilConnection = errors.New("database connection is nil")
	// ErrInvalidDriver indicates an unsupported database driver
	ErrInvalidDriver = errors.New("invalid or unsupported database driver")
)

// Config holds database configuration
type Config struct {
	Driver          string
	DSN             string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	ConnMaxIdleTime time.Duration
	AutoMigrate     bool
	MigrationsPath  string        // Path to migrations directory
	MaxRetries      int           // Maximum connection retry attempts
	RetryDelay      time.Duration // Delay between retries
	QueryTimeout    time.Duration // Default query timeout
}

// Database wraps the SQL DB connection with lifecycle management
type Database struct {
	DB     *sql.DB
	config Config
	mu     sync.RWMutex
	closed bool
}

// New creates a new database connection with retry logic and validation
func New(cfg Config) (*Database, error) {
	// Validate configuration
	if err := validateConfig(&cfg); err != nil {
		return nil, fmt.Errorf("invalid config: %w", err)
	}

	// Set defaults
	setConfigDefaults(&cfg)

	var conn *sql.DB
	var err error

	// Retry logic for a connection establishment
	maxRetries := cfg.MaxRetries
	if maxRetries <= 0 {
		maxRetries = 3
	}

	runtimeDriver := runtimeSQLDriver(cfg.Driver)

	for attempt := 1; attempt <= maxRetries; attempt++ {
		conn, err = sql.Open(runtimeDriver, cfg.DSN)
		if err != nil {
			if attempt < maxRetries {
				log.Printf("⚠️  Database connection attempt %d/%d failed: %v. Retrying in %v...",
					attempt, maxRetries, err, cfg.RetryDelay)
				time.Sleep(cfg.RetryDelay)
				continue
			}
			return nil, fmt.Errorf("failed to open database after %d attempts: %w", maxRetries, err)
		}

		// Test connection with context
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		err = conn.PingContext(ctx)
		cancel()

		if err != nil {
			// try to close the opened connection, ignore error
			if conn != nil {
				_ = conn.Close()
			}
			if attempt < maxRetries {
				log.Printf("⚠️  Database ping attempt %d/%d failed: %v. Retrying in %v...",
					attempt, maxRetries, err, cfg.RetryDelay)
				time.Sleep(cfg.RetryDelay)
				continue
			}
			return nil, fmt.Errorf("failed to ping database after %d attempts: %w", maxRetries, err)
		}

		// Success
		break
	}

	// Run migrations if requested
	if cfg.AutoMigrate {
		if err := runMigrations(cfg); err != nil {
			if conn != nil {
				_ = conn.Close()
			}
			return nil, fmt.Errorf("migration failed: %w", err)
		}
	}

	// Configure connection pool
	if conn != nil {
		configureConnectionPool(conn, cfg)
	}

	db := &Database{
		DB:     conn,
		config: cfg,
		closed: false,
	}

	// Log successful connection with sanitized DSN
	sanitizedDSN := sanitizeDSN(cfg.DSN)
	log.Printf("✅ Database connected successfully (%s): %s", runtimeDriver, sanitizedDSN)
	if conn != nil {
		stats := conn.Stats()
		log.Printf("📊 Connection pool: max_open=%d, max_idle=%d, lifetime=%v, idle_timeout=%v, current_open=%d",
			cfg.MaxOpenConns, cfg.MaxIdleConns, cfg.ConnMaxLifetime, cfg.ConnMaxIdleTime, stats.OpenConnections)
	} else {
		log.Printf("📊 Connection pool: connection is nil (unexpected)")
	}

	return db, nil
}

func runtimeSQLDriver(configDriver string) string {
	d := strings.ToLower(strings.TrimSpace(configDriver))
	if d == "mariadb" {
		return "mysql"
	}
	if d == "postgresql" {
		return "postgres"
	}
	return d
}

// GetConnection returns the raw SQL DB connection (thread-safe)
func (d *Database) GetConnection() (*sql.DB, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.closed {
		return nil, errors.New("database connection is closed")
	}
	if d.DB == nil {
		return nil, ErrNilConnection
	}
	return d.DB, nil
}

// Close closes the database connection gracefully (idempotent)
func (d *Database) Close() error {
	d.mu.Lock()
	defer d.mu.Unlock()

	if d.closed {
		return nil // Already closed
	}

	if d.DB != nil {
		log.Println("🔌 Closing database connection...")
		if err := d.DB.Close(); err != nil {
			return fmt.Errorf("failed to close database: %w", err)
		}
		d.closed = true
		log.Println("✅ Database connection closed successfully")
	}
	return nil
}

// IsClosed returns true if the database connection is closed
func (d *Database) IsClosed() bool {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.closed
}

// Ping checks if the database is still accessible
func (d *Database) Ping() error {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.closed {
		return errors.New("database connection is closed")
	}
	if d.DB == nil {
		return ErrNilConnection
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	return d.DB.PingContext(ctx)
}

// Health checks database health and returns detailed status
func (d *Database) Health() error {
	if err := d.Ping(); err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}

	stats := d.GetStats()
	if stats.OpenConnections == 0 {
		return errors.New("no open connections available")
	}

	return nil
}

// GetStats returns current connection pool statistics (thread-safe)
func (d *Database) GetStats() sql.DBStats {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.DB != nil && !d.closed {
		return d.DB.Stats()
	}
	return sql.DBStats{}
}

// Driver returns the database driver name.
func (d *Database) Driver() string {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.config.Driver
}

// Query executes a SELECT query with timeout and validation
func (d *Database) Query(query string, args ...interface{}) (*sql.Rows, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.closed {
		return nil, errors.New("database connection is closed")
	}
	if d.DB == nil {
		return nil, ErrNilConnection
	}

	timeout := d.config.QueryTimeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	//nolint:sqlclosecheck // callers own the returned *sql.Rows lifecycle
	return d.DB.QueryContext(ctx, query, args...)
}

// QueryRow executes a SELECT query returning a single row
func (d *Database) QueryRow(query string, args ...interface{}) (*sql.Row, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.closed {
		return nil, errors.New("database connection is closed")
	}
	if d.DB == nil {
		return nil, ErrNilConnection
	}

	timeout := d.config.QueryTimeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	return d.DB.QueryRowContext(ctx, query, args...), nil
}

// Exec executes an INSERT, UPDATE, or DELETE query
func (d *Database) Exec(query string, args ...interface{}) (sql.Result, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.closed {
		return nil, errors.New("database connection is closed")
	}
	if d.DB == nil {
		return nil, ErrNilConnection
	}

	timeout := d.config.QueryTimeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	return d.DB.ExecContext(ctx, query, args...)
}

// BeginTx starts a new database transaction with context
func (d *Database) BeginTx(ctx context.Context, opts *sql.TxOptions) (*sql.Tx, error) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	if d.closed {
		return nil, errors.New("database connection is closed")
	}
	if d.DB == nil {
		return nil, ErrNilConnection
	}

	if ctx == nil {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
	}

	return d.DB.BeginTx(ctx, opts)
}

// Helper functions

// validateConfig validates database configuration
func validateConfig(cfg *Config) error {
	if cfg.DSN == "" {
		return errors.New("DSN cannot be empty")
	}

	validDrivers := map[string]bool{
		"mysql":      true,
		"mariadb":    true,
		"postgres":   true,
		"postgresql": true,
	}

	d := strings.ToLower(strings.TrimSpace(cfg.Driver))
	if d == "" {
		cfg.Driver = "postgres"
	} else if !validDrivers[d] {
		return fmt.Errorf("%w: %s (supported: mysql, mariadb, postgres, postgresql)", ErrInvalidDriver, cfg.Driver)
	} else {
		cfg.Driver = runtimeSQLDriver(d)
	}

	if cfg.MaxOpenConns < 0 || cfg.MaxIdleConns < 0 {
		return errors.New("connection pool values cannot be negative")
	}

	if cfg.MaxIdleConns > cfg.MaxOpenConns && cfg.MaxOpenConns > 0 {
		return errors.New("MaxIdleConns cannot exceed MaxOpenConns")
	}

	return nil
}

// setConfigDefaults sets default values for configuration
func setConfigDefaults(cfg *Config) {
	if cfg.MaxOpenConns == 0 {
		cfg.MaxOpenConns = 25
	}
	if cfg.MaxIdleConns == 0 {
		cfg.MaxIdleConns = 5
	}
	if cfg.MaxIdleConns > cfg.MaxOpenConns && cfg.MaxOpenConns > 0 {
		cfg.MaxIdleConns = cfg.MaxOpenConns
	}
	if cfg.ConnMaxLifetime == 0 {
		cfg.ConnMaxLifetime = 5 * time.Minute
	}
	if cfg.ConnMaxIdleTime == 0 {
		cfg.ConnMaxIdleTime = 2 * time.Minute
	}
	if cfg.RetryDelay == 0 {
		cfg.RetryDelay = 2 * time.Second
	}
	if cfg.QueryTimeout == 0 {
		cfg.QueryTimeout = 30 * time.Second
	}
	if cfg.MigrationsPath == "" {
		cfg.MigrationsPath = defaultMigrationsPathForDriver(cfg.Driver)
	}
}

func defaultMigrationsPathForDriver(driver string) string {
	switch strings.ToLower(strings.TrimSpace(driver)) {
	case "postgres":
		return "migrations/postgres"
	default:
		return "migrations/mysql"
	}
}

// configureConnectionPool configures the database connection pool
func configureConnectionPool(conn *sql.DB, cfg Config) {
	conn.SetMaxOpenConns(cfg.MaxOpenConns)
	conn.SetMaxIdleConns(cfg.MaxIdleConns)
	conn.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	conn.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)
}

// runMigrations runs database migrations
func runMigrations(cfg Config) error {
	sourceURL := "file://" + cfg.MigrationsPath

	// Build database URL based on driver
	dbURL, err := BuildMigrateDatabaseURL(cfg)
	if err != nil {
		return fmt.Errorf("failed to build migrate database url: %w", err)
	}

	m, err := migrate.New(sourceURL, dbURL)
	if err != nil {
		// If there's an error creating the migrate instance, it might be due to an invalid migration state
		// Try to recover by forcing the version
		errStr := err.Error()
		if strings.Contains(strings.ToLower(errStr), "no migration found") {
			log.Printf("⚠️  Migration state issue detected: %v. Attempting recovery...", err)
			// Create a temporary instance just to fix the state
			tempM, tempErr := migrate.New(sourceURL, dbURL)
			if tempErr == nil {
				defer func(tempM *migrate.Migrate) {
					err, _ := tempM.Close()
					if err != nil {
						log.Printf("⚠️  Failed to close temporary migrate instance: %v", err)
					}
				}(tempM)
				// Get current version
				ver, _, verErr := tempM.Version()
				if verErr == nil {
					log.Printf("⚠️  Forcing version %d to resolve migration state...", ver)
					if fErr := tempM.Force(int(ver)); fErr == nil {
						log.Printf("✅ Migration state recovered. Retrying...")
						// Retry creating the migrated instance
						m, err = migrate.New(sourceURL, dbURL)
					}
				}
			}
		}
		if err != nil {
			return fmt.Errorf("failed to create migrate instance: %w", err)
		}
	}
	defer func() {
		srcErr, dbErr := m.Close()
		if srcErr != nil || dbErr != nil {
			log.Printf("⚠️  Failed to close migrate resources: source=%v db=%v", srcErr, dbErr)
		}
	}()

	// Run migrations with recovery for common partial-state issues.
	// This helps when historical migrations contain non-idempotent index creation
	// and the schema already has those relations from prior runs.
	const maxRecoveryAttempts = 10
	for attempt := 1; attempt <= maxRecoveryAttempts; attempt++ {
		err := m.Up()
		if err == nil || errors.Is(err, migrate.ErrNoChange) {
			log.Println("✅ Database migrations applied successfully")
			return nil
		}

		errLower := strings.ToLower(err.Error())
		isRecoverable := strings.Contains(errLower, "dirty") ||
			strings.Contains(errLower, "no migration found") ||
			isAlreadyExistsMigrationError(errLower)

		if !isRecoverable {
			return fmt.Errorf("migration execution failed: %w", err)
		}
		if !migrationForceRecoveryAllowed() {
			return fmt.Errorf("migration execution failed with recoverable state but automatic force recovery is disabled in production: %w", err)
		}

		ver, _, vErr := m.Version()
		if vErr != nil {
			return fmt.Errorf("migration failed and could not read version: %w", errors.Join(vErr, err))
		}

		log.Printf("⚠️  Recoverable migration issue at version %d (attempt %d/%d): %v", ver, attempt, maxRecoveryAttempts, err)
		if fErr := m.Force(int(ver)); fErr != nil {
			return fmt.Errorf("failed to force migration version %d: %w", ver, errors.Join(fErr, err))
		}
		log.Printf("⚠️  Forced migration version %d, retrying up...", ver)
	}

	return fmt.Errorf("migration recovery attempts exceeded (%d)", maxRecoveryAttempts)
}

// isAlreadyExistsMigrationError identifies duplicate object errors from non-idempotent migrations.
func isAlreadyExistsMigrationError(errLower string) bool {
	if !strings.Contains(errLower, "already exists") {
		return false
	}

	return strings.Contains(errLower, "relation") ||
		strings.Contains(errLower, "index") ||
		strings.Contains(errLower, "constraint") ||
		strings.Contains(errLower, "column") ||
		strings.Contains(errLower, "table")
}

func migrationForceRecoveryAllowed() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("DB_MIGRATION_FORCE_RECOVERY"))) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	}

	for _, key := range []string{"APP_CONFIG_ENV", "APP_ENV", "ENVIRONMENT"} {
		switch strings.ToLower(strings.TrimSpace(os.Getenv(key))) {
		case "production", "prod":
			return false
		}
	}
	return true
}

// BuildMigrateDatabaseURL converts cfg.Driver and cfg.DSN into a URL acceptable by golang-migrate
func BuildMigrateDatabaseURL(cfg Config) (string, error) {
	driver := strings.ToLower(cfg.Driver)
	dsn := strings.TrimSpace(cfg.DSN)

	if strings.Contains(driver, "mysql") || strings.Contains(driver, "mariadb") {
		// If already a URL, return as-is (golang-migrate for MySQL uses tcp://)
		if strings.HasPrefix(dsn, "mysql://") {
			return dsn, nil
		}

		// go-sql-driver/mysql DSN is typically: user:password@tcp(localhost:3306)/dbname
		// golang-migrate expects: mysql://user:password@tcp(localhost:3306)/dbname
		if strings.HasPrefix(dsn, "tcp(") || strings.Contains(dsn, "@tcp(") {
			return "mysql://" + dsn, nil
		}

		return "mysql://" + dsn, nil
	}

	if strings.Contains(driver, "postgres") {
		if strings.HasPrefix(dsn, "postgres://") || strings.HasPrefix(dsn, "postgresql://") {
			return dsn, nil
		}
		if strings.HasPrefix(dsn, "host=") || strings.HasPrefix(dsn, "postgres") {
			return "postgres://" + dsn, nil
		}
		return "postgres://" + dsn, nil
	}

	return "", fmt.Errorf("unsupported driver for migrations: %s", cfg.Driver)
}

// sanitizeDSN removes sensitive information from DSN for logging
func sanitizeDSN(dsn string) string {
	if strings.Contains(dsn, "password=") {
		parts := strings.Split(dsn, " ")
		for i, part := range parts {
			if strings.HasPrefix(part, "password=") {
				parts[i] = "password=***"
			}
		}
		return strings.Join(parts, " ")
	}

	// For URLs with passwords
	if strings.Contains(dsn, "://") && strings.Contains(dsn, "@") {
		parts := strings.SplitN(dsn, "://", 2)
		if len(parts) == 2 {
			userParts := strings.SplitN(parts[1], "@", 2)
			if len(userParts) == 2 {
				credentials := strings.SplitN(userParts[0], ":", 2)
				if len(credentials) == 2 {
					return parts[0] + "://" + credentials[0] + ":***@" + userParts[1]
				}
			}
		}
	}

	// For other non-sensitive DSNs, return as-is (or truncate if too long)
	if len(dsn) > 100 {
		return dsn[:100] + "..."
	}
	return dsn
}
