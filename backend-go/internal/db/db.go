package db

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "github.com/lib/pq"
	_ "github.com/mattn/go-sqlite3"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/database/sqlite3"
	_ "github.com/golang-migrate/migrate/v4/source/file"
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
}

// Database wraps the SQL DB connection
type Database struct {
	DB *sql.DB
}

// New creates a new database connection with pure SQL
func New(cfg Config) (*Database, error) {
	if cfg.Driver == "" {
		cfg.Driver = "sqlite3"
	}

	conn, err := sql.Open(cfg.Driver, cfg.DSN)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test connection
	if err := conn.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Run migrations if requested
	if cfg.AutoMigrate {
		// Build source URL (migrations directory) and DB URL depending on driver
		sourceURL := "file://migrations"
		var dbURL string

		if strings.HasPrefix(cfg.Driver, "sqlite") || strings.Contains(cfg.Driver, "sqlite") {
			// Make DSN absolute so migrate can find sqlite file
			dsn := cfg.DSN
			if !strings.HasPrefix(dsn, "/") {
				cwd, _ := os.Getwd()
				dsn = filepath.Join(cwd, dsn)
			}
			// For sqlite, use the connection string with driver
			dbURL = "sqlite3://" + dsn
		} else if strings.HasPrefix(cfg.Driver, "postgres") || strings.Contains(cfg.Driver, "postgres") {
			// For postgres
			dbURL = cfg.DSN
		}

		if dbURL != "" {
			m, err := migrate.New(sourceURL, dbURL)
			if err != nil {
				log.Printf("⚠️  Migration setup failed: %v (continuing with server startup)", err)
			} else {
				defer func() {
					srcErr, dbErr := m.Close()
					if srcErr != nil || dbErr != nil {
						log.Printf("⚠️  failed to close migrate: source=%v db=%v", srcErr, dbErr)
					}
				}()
				if err := m.Up(); err != nil && err != migrate.ErrNoChange {
					log.Printf("⚠️  Migrations failed: %v (continuing with server startup)", err)
				} else {
					log.Println("✅ Migrations applied successfully")
				}
			}
		}
	}

	// Configure connection pool
	// MaxOpenConns: maximum number of open connections to the database
	if cfg.MaxOpenConns > 0 {
		conn.SetMaxOpenConns(cfg.MaxOpenConns)
	} else {
		conn.SetMaxOpenConns(25) // default: suitable for moderate load
	}

	// MaxIdleConns: maximum number of idle connections
	if cfg.MaxIdleConns > 0 {
		conn.SetMaxIdleConns(cfg.MaxIdleConns)
	} else {
		conn.SetMaxIdleConns(5) // default: keep some warm connections
	}

	// ConnMaxLifetime: maximum lifetime of a connection (prevents stale connections)
	if cfg.ConnMaxLifetime > 0 {
		conn.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	} else {
		conn.SetConnMaxLifetime(5 * time.Minute) // default: recycle connections after 5 min
	}

	// ConnMaxIdleTime: maximum idle time before connection is closed (reduces resource usage)
	if cfg.ConnMaxIdleTime > 0 {
		conn.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)
	} else {
		conn.SetConnMaxIdleTime(2 * time.Minute) // default: close idle connections after 2 min
	}

	log.Printf("✅ Database connected successfully (%s)", cfg.Driver)
	log.Printf("📊 Connection pool: max_open=%d, max_idle=%d, lifetime=%v, idle_timeout=%v",
		conn.Stats().OpenConnections, cfg.MaxIdleConns, cfg.ConnMaxLifetime, cfg.ConnMaxIdleTime)
	return &Database{DB: conn}, nil
}

// GetConnection returns the raw SQL DB connection
func (d *Database) GetConnection() *sql.DB {
	return d.DB
}

// Close closes the database connection
func (d *Database) Close() error {
	if d.DB != nil {
		return d.DB.Close()
	}
	return nil
}

// Ping checks if the database is still accessible
func (d *Database) Ping() error {
	if d.DB == nil {
		return fmt.Errorf("database connection is nil")
	}
	ctx, cancel := contextWithTimeout(5 * time.Second)
	defer cancel()
	return d.DB.PingContext(ctx)
}

// Health checks database health
func (d *Database) Health() error {
	return d.Ping()
}

// GetStats returns current connection pool statistics
func (d *Database) GetStats() sql.DBStats {
	if d.DB != nil {
		return d.DB.Stats()
	}
	return sql.DBStats{}
}

// contextWithTimeout returns a context with timeout
func contextWithTimeout(timeout time.Duration) (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), timeout)
}

// Query executes a SELECT query
func (d *Database) Query(query string, args ...interface{}) (*sql.Rows, error) {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.DB.QueryContext(ctx, query, args...)
}

// QueryRow executes a SELECT query returning a single row
func (d *Database) QueryRow(query string, args ...interface{}) *sql.Row {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.DB.QueryRowContext(ctx, query, args...)
}

// Exec executes an INSERT, UPDATE, or DELETE query
func (d *Database) Exec(query string, args ...interface{}) (sql.Result, error) {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.DB.ExecContext(ctx, query, args...)
}

// BeginTx starts a new database transaction
func (d *Database) BeginTx() (*sql.Tx, error) {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.DB.BeginTx(ctx, nil)
}

// Database initialization handles migrations via golang-migrate
// Table creation is managed by migration files in migrations/ directory
