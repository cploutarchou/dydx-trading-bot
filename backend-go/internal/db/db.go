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
	_ "github.com/golang-migrate/migrate/v4/database/sqlite"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

// Config holds database configuration
type Config struct {
	Driver          string
	DSN             string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	// AutoMigrate controls whether to run migrations using golang-migrate
	AutoMigrate bool
}

// Database wraps the SQL DB connection
type Database struct {
	conn *sql.DB
}

// New creates a new database connection with pure SQL
func New(cfg Config) (*Database, error) {
	if cfg.Driver == "" {
		cfg.Driver = "postgres"
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
				defer m.Close()
				if err := m.Up(); err != nil && err != migrate.ErrNoChange {
					log.Printf("⚠️  Migrations failed: %v (continuing with server startup)", err)
				} else {
					log.Println("✅ Migrations applied successfully")
				}
			}
		}
	}

	// Configure connection pool
	if cfg.MaxOpenConns > 0 {
		conn.SetMaxOpenConns(cfg.MaxOpenConns)
	} else {
		conn.SetMaxOpenConns(25)
	}

	if cfg.MaxIdleConns > 0 {
		conn.SetMaxIdleConns(cfg.MaxIdleConns)
	} else {
		conn.SetMaxIdleConns(5)
	}

	if cfg.ConnMaxLifetime > 0 {
		conn.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	} else {
		conn.SetConnMaxLifetime(5 * time.Minute)
	}

	log.Printf("✅ Database connected successfully (%s)", cfg.Driver)
	return &Database{conn: conn}, nil
}

// GetConnection returns the raw SQL DB connection
func (d *Database) GetConnection() *sql.DB {
	return d.conn
}

// Close closes the database connection
func (d *Database) Close() error {
	if d.conn != nil {
		return d.conn.Close()
	}
	return nil
}

// Ping checks if the database is still accessible
func (d *Database) Ping() error {
	if d.conn == nil {
		return fmt.Errorf("database connection is nil")
	}
	ctx, cancel := contextWithTimeout(5 * time.Second)
	defer cancel()
	return d.conn.PingContext(ctx)
}

// Health checks database health and returns detailed info
func (d *Database) Health() map[string]interface{} {
	stats := d.conn.Stats()
	return map[string]interface{}{
		"connected":           d.Ping() == nil,
		"open_connections":    stats.OpenConnections,
		"in_use":              stats.InUse,
		"idle":                stats.Idle,
		"wait_count":          stats.WaitCount,
		"wait_duration":       stats.WaitDuration.String(),
		"max_idle_closed":     stats.MaxIdleClosed,
		"max_lifetime_closed": stats.MaxLifetimeClosed,
	}
}

// contextWithTimeout returns a context with timeout
func contextWithTimeout(timeout time.Duration) (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), timeout)
}

// Query executes a SELECT query
func (d *Database) Query(query string, args ...interface{}) (*sql.Rows, error) {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.conn.QueryContext(ctx, query, args...)
}

// QueryRow executes a SELECT query returning a single row
func (d *Database) QueryRow(query string, args ...interface{}) *sql.Row {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.conn.QueryRowContext(ctx, query, args...)
}

// Exec executes an INSERT, UPDATE, or DELETE query
func (d *Database) Exec(query string, args ...interface{}) (sql.Result, error) {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.conn.ExecContext(ctx, query, args...)
}

// BeginTx starts a new database transaction
func (d *Database) BeginTx() (*sql.Tx, error) {
	ctx, cancel := contextWithTimeout(30 * time.Second)
	defer cancel()
	return d.conn.BeginTx(ctx, nil)
}

// Database initialization handles migrations via golang-migrate
// Table creation is managed by migration files in migrations/ directory
