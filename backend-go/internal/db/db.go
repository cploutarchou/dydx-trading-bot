package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	_ "github.com/lib/pq"
	_ "github.com/mattn/go-sqlite3"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/database/sqlite3"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

var (
	// DB is the global database instance (deprecated: use dependency injection instead)
	DB *Database
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

	// Retry logic for connection establishment
	maxRetries := cfg.MaxRetries
	if maxRetries <= 0 {
		maxRetries = 3
	}

	for attempt := 1; attempt <= maxRetries; attempt++ {
		conn, err = sql.Open(cfg.Driver, cfg.DSN)
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
			conn.Close()
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
			conn.Close()
			return nil, fmt.Errorf("migration failed: %w", err)
		}
	}

	// Configure connection pool
	configureConnectionPool(conn, cfg)

	db := &Database{
		DB:     conn,
		config: cfg,
		closed: false,
	}

	// Log successful connection with sanitized DSN
	sanitizedDSN := sanitizeDSN(cfg.DSN)
	log.Printf("✅ Database connected successfully (%s): %s", cfg.Driver, sanitizedDSN)
	stats := conn.Stats()
	log.Printf("📊 Connection pool: max_open=%d, max_idle=%d, lifetime=%v, idle_timeout=%v, current_open=%d",
		cfg.MaxOpenConns, cfg.MaxIdleConns, cfg.ConnMaxLifetime, cfg.ConnMaxIdleTime, stats.OpenConnections)

	return db, nil
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
		"sqlite3":  true,
		"sqlite":   true,
		"postgres": true,
		"pgx":      true,
	}

	if cfg.Driver == "" {
		cfg.Driver = "sqlite3" // Default
	} else if !validDrivers[cfg.Driver] {
		return fmt.Errorf("%w: %s (supported: sqlite3, postgres)", ErrInvalidDriver, cfg.Driver)
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
		cfg.MigrationsPath = "migrations"
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
	var dbURL string

	// Build database URL based on driver
	if strings.HasPrefix(cfg.Driver, "sqlite") || strings.Contains(cfg.Driver, "sqlite") {
		dsn := cfg.DSN
		if !strings.HasPrefix(dsn, "/") && !strings.HasPrefix(dsn, ":memory:") {
			cwd, err := os.Getwd()
			if err != nil {
				return fmt.Errorf("failed to get working directory: %w", err)
			}
			dsn = filepath.Join(cwd, dsn)
		}
		dbURL = "sqlite3://" + dsn
	} else if strings.HasPrefix(cfg.Driver, "postgres") || strings.Contains(cfg.Driver, "postgres") {
		dbURL = cfg.DSN
	} else {
		return fmt.Errorf("unsupported driver for migrations: %s", cfg.Driver)
	}

	m, err := migrate.New(sourceURL, dbURL)
	if err != nil {
		return fmt.Errorf("migration setup failed: %w", err)
	}
	defer func() {
		srcErr, dbErr := m.Close()
		if srcErr != nil || dbErr != nil {
			log.Printf("⚠️  Failed to close migrate resources: source=%v db=%v", srcErr, dbErr)
		}
	}()

	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return fmt.Errorf("migration execution failed: %w", err)
	}

	log.Println("✅ Database migrations applied successfully")
	return nil
}

// sanitizeDSN removes sensitive information from DSN for logging
func sanitizeDSN(dsn string) string {
	// For PostgreSQL connection strings
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
		// postgres://user:password@host/db -> postgres://user:***@host/db
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

	// For SQLite or other non-sensitive DSNs, return as-is (or truncate if too long)
	if len(dsn) > 100 {
		return dsn[:100] + "..."
	}
	return dsn
}
