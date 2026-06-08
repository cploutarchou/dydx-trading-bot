package db

import "testing"

func TestSetConfigDefaultsUsesCorrectMigrationPath_MariaDB(t *testing.T) {
	cfg := Config{Driver: "mysql", DSN: "user:pass@tcp(localhost:3306)/test"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 25 {
		t.Fatalf("expected MaxOpenConns=25, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Fatalf("expected MaxIdleConns=5, got %d", cfg.MaxIdleConns)
	}
	if cfg.MigrationsPath != "migrations/mysql" {
		t.Fatalf("expected MySQL migrations path, got %q", cfg.MigrationsPath)
	}
}

func TestSetConfigDefaultsUsesMySQLPoolSizes(t *testing.T) {
	cfg := Config{Driver: "mysql", DSN: "mysql://localhost/test"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 25 {
		t.Fatalf("expected mysql MaxOpenConns=25, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Fatalf("expected mysql MaxIdleConns=5, got %d", cfg.MaxIdleConns)
	}
	if cfg.MigrationsPath != "migrations/mysql" {
		t.Fatalf("expected mysql migrations path, got %q", cfg.MigrationsPath)
	}
}

func TestSetConfigDefaultsKeepsMySQLPoolDefaults(t *testing.T) {
	cfg := Config{Driver: "mysql", DSN: "mysql://localhost/test"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 25 {
		t.Fatalf("expected mysql MaxOpenConns=25, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Fatalf("expected mysql MaxIdleConns=5, got %d", cfg.MaxIdleConns)
	}
}

func TestValidateConfigRejectsUnsupportedDrivers(t *testing.T) {
	cfg := Config{Driver: "sqlite", DSN: "file:test.db"}

	if err := validateConfig(&cfg); err == nil {
		t.Fatal("expected sqlite driver to be rejected")
	}
}

func TestValidateConfigRejectsLegacyDrivers(t *testing.T) {
	unsupported := "post" + "gres"
	cfg := Config{Driver: unsupported, DSN: unsupported + "://localhost/test"}

	if err := validateConfig(&cfg); err == nil {
		t.Fatal("expected unsupported legacy driver to be rejected")
	}
}
