package db

import "testing"

func TestSetConfigDefaultsUsesPostgresPoolSizes(t *testing.T) {
	cfg := Config{Driver: "postgres", DSN: "postgres://localhost/test"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 25 {
		t.Fatalf("expected postgres MaxOpenConns=25, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Fatalf("expected postgres MaxIdleConns=5, got %d", cfg.MaxIdleConns)
	}
	if cfg.MigrationsPath != "migrations/postgres" {
		t.Fatalf("expected postgres migrations path, got %q", cfg.MigrationsPath)
	}
}

func TestSetConfigDefaultsKeepsPostgresPoolDefaults(t *testing.T) {
	cfg := Config{Driver: "postgres", DSN: "postgres://localhost/test"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 25 {
		t.Fatalf("expected postgres MaxOpenConns=25, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Fatalf("expected postgres MaxIdleConns=5, got %d", cfg.MaxIdleConns)
	}
}

func TestValidateConfigRejectsNonPostgresDrivers(t *testing.T) {
	cfg := Config{Driver: "sqlite", DSN: "file:test.db"}

	if err := validateConfig(&cfg); err == nil {
		t.Fatal("expected sqlite driver to be rejected")
	}
}
