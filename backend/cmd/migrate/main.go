package main

import (
	"errors"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/golang-migrate/migrate/v4"
)

func loadRuntimeConfig() error {
	if err := config.LoadFileEnvValues(true); err != nil {
		return fmt.Errorf("load file-backed environment values: %w", err)
	}
	if strings.EqualFold(os.Getenv("MIGRATION_SKIP_STRUCTURED_CONFIG"), "true") {
		log.Printf("Structured config loading skipped for migration command")
	} else if _, err := config.AutoLoadStructuredConfigEnv(true); err != nil {
		log.Printf("Structured config not loaded; using process environment: %v", err)
	}
	if err := config.LoadFileEnvValues(true); err != nil {
		return fmt.Errorf("reload file-backed environment values: %w", err)
	}
	if err := config.LoadConfig(); err != nil {
		return fmt.Errorf("load config: %w", err)
	}
	return nil
}

func newMigrator() (*migrate.Migrate, error) {
	if err := loadRuntimeConfig(); err != nil {
		return nil, err
	}

	dbCfg := db.Config{
		Driver:         config.ConfigInstance.Database.Type,
		DSN:            config.ConfigInstance.Database.DSN(),
		MigrationsPath: config.ConfigInstance.Database.MigrationsPath(),
	}
	databaseURL, err := db.BuildMigrateDatabaseURL(dbCfg)
	if err != nil {
		return nil, fmt.Errorf("build migration database URL: %w", err)
	}

	m, err := migrate.New("file://"+dbCfg.MigrationsPath, databaseURL)
	if err != nil {
		return nil, fmt.Errorf("create migrator: %w", err)
	}
	return m, nil
}

func printVersion(m *migrate.Migrate) error {
	version, dirty, err := m.Version()
	if err != nil {
		if errors.Is(err, migrate.ErrNilVersion) {
			fmt.Println("version=0 dirty=false")
			return nil
		}
		return fmt.Errorf("read migration version: %w", err)
	}
	fmt.Printf("version=%d dirty=%t\n", version, dirty)
	return nil
}

func run() error {
	command := "status"
	if len(os.Args) > 1 {
		command = strings.ToLower(strings.TrimSpace(os.Args[1]))
	}

	m, err := newMigrator()
	if err != nil {
		return err
	}
	defer func() {
		srcErr, dbErr := m.Close()
		if srcErr != nil || dbErr != nil {
			log.Printf("failed to close migration resources: source=%v db=%v", srcErr, dbErr)
		}
	}()

	switch command {
	case "up":
		if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
			return fmt.Errorf("apply migrations: %w", err)
		}
		return printVersion(m)
	case "down":
		steps := 1
		if len(os.Args) > 2 {
			parsed, parseErr := strconv.Atoi(os.Args[2])
			if parseErr != nil || parsed <= 0 {
				return fmt.Errorf("down step count must be a positive integer")
			}
			steps = parsed
		}
		if err := m.Steps(-steps); err != nil && !errors.Is(err, migrate.ErrNoChange) {
			return fmt.Errorf("roll back %d migration(s): %w", steps, err)
		}
		return printVersion(m)
	case "version", "status":
		return printVersion(m)
	default:
		return fmt.Errorf("unknown command %q; use up, down [steps], version, or status", command)
	}
}

func main() {
	if err := run(); err != nil {
		log.Printf("migration command failed: %v", err)
		os.Exit(1)
	}
}
