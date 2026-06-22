package db

import "testing"

func TestSetConfigDefaultsUsesCorrectMigrationPath_Postgres(t *testing.T) {
	cfg := Config{Driver: "postgres", DSN: "postgres://user:pass@localhost:5432/test"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 25 {
		t.Fatalf("expected MaxOpenConns=25, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 5 {
		t.Fatalf("expected MaxIdleConns=5, got %d", cfg.MaxIdleConns)
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

func TestValidateConfigRejectsUnsupportedDrivers(t *testing.T) {
	cfg := Config{Driver: "sqlite", DSN: "file:test.db"}

	if err := validateConfig(&cfg); err == nil {
		t.Fatal("expected sqlite driver to be rejected")
	}
}

func TestValidateConfigAcceptsLegacyPostgresAlias(t *testing.T) {
	legacy := "post" + "gresql"
	cfg := Config{Driver: legacy, DSN: legacy + "://localhost/test"}

	if err := validateConfig(&cfg); err != nil {
		t.Fatalf("expected legacy postgres alias to be accepted, got %v", err)
	}
	if cfg.Driver != "postgres" {
		t.Fatalf("expected postgres normalization, got %q", cfg.Driver)
	}
}

func TestValidateConfigAcceptsPostgres(t *testing.T) {
	cfg := Config{Driver: "postgresql", DSN: "postgres://user:pass@localhost:5432/test"}

	if err := validateConfig(&cfg); err != nil {
		t.Fatalf("expected postgres driver to be accepted, got %v", err)
	}
	if cfg.Driver != "postgres" {
		t.Fatalf("expected postgres driver normalization, got %q", cfg.Driver)
	}
}

func TestBuildMigrateDatabaseURL_Postgres(t *testing.T) {
	url, err := BuildMigrateDatabaseURL(Config{Driver: "postgres", DSN: "postgres://user:pass@localhost:5432/test"})
	if err != nil {
		t.Fatalf("BuildMigrateDatabaseURL returned error: %v", err)
	}
	if url != "postgres://user:pass@localhost:5432/test" {
		t.Fatalf("expected postgres URL to pass through, got %q", url)
	}
}
