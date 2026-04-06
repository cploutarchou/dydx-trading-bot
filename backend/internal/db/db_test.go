package db

import "testing"

func TestSetConfigDefaultsUsesSQLiteSafePoolSizes(t *testing.T) {
	cfg := Config{Driver: "sqlite", DSN: "file:test.db"}
	setConfigDefaults(&cfg)

	if cfg.MaxOpenConns != 1 {
		t.Fatalf("expected sqlite MaxOpenConns=1, got %d", cfg.MaxOpenConns)
	}
	if cfg.MaxIdleConns != 1 {
		t.Fatalf("expected sqlite MaxIdleConns=1, got %d", cfg.MaxIdleConns)
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
