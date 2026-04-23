package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindRepoRootPrefersMonorepoRootWithStructuredConfig(t *testing.T) {
	base := t.TempDir()

	workspaceRoot := filepath.Join(base, "workspace")
	backendRoot := filepath.Join(workspaceRoot, "backend")

	for _, dir := range []string{
		filepath.Join(workspaceRoot, ".github"),
		filepath.Join(workspaceRoot, "config", "profiles"),
		filepath.Join(backendRoot, ".github"),
	} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatalf("mkdir %s: %v", dir, err)
		}
	}

	for _, file := range []string{
		filepath.Join(workspaceRoot, "AGENTS.md"),
		filepath.Join(backendRoot, "AGENTS.md"),
	} {
		if err := os.WriteFile(file, []byte("test"), 0o644); err != nil {
			t.Fatalf("write %s: %v", file, err)
		}
	}

	got := FindRepoRoot(backendRoot)
	if got != workspaceRoot {
		t.Fatalf("expected monorepo root %s, got %s", workspaceRoot, got)
	}
}

func TestLoadConfig_UsesPostgresByDefault(t *testing.T) {
	t.Setenv("APP_ENV", "test")
	t.Setenv("DB_TYPE", "postgres")

	defer func() {
		ConfigInstance = nil
	}()

	if err := LoadConfig(); err != nil {
		t.Fatalf("LoadConfig returned error: %v", err)
	}

	if ConfigInstance == nil {
		t.Fatal("expected ConfigInstance to be initialized")
	}
	if got := ConfigInstance.Database.Type; got != "postgres" {
		t.Fatalf("expected postgres database type, got %q", got)
	}
}

func TestLoadConfig_ReturnsErrorForUnsupportedDBType(t *testing.T) {
	t.Setenv("APP_ENV", "development")
	t.Setenv("DB_TYPE", "sqlite3")

	defer func() {
		ConfigInstance = nil
	}()

	err := LoadConfig()
	if err == nil {
		t.Fatal("expected LoadConfig to return an error for sqlite3")
	}
}
