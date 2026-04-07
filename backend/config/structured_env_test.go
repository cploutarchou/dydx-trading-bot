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

func TestLoadConfig_AllowsSQLiteInTestEnv(t *testing.T) {
	t.Setenv("APP_ENV", "test")
	t.Setenv("DB_TYPE", "sqlite3")
	t.Setenv("DB_NAME", ":memory:")

	defer func() {
		ConfigInstance = nil
	}()

	LoadConfig()

	if ConfigInstance == nil {
		t.Fatal("expected ConfigInstance to be initialized")
	}
	if got := ConfigInstance.Database.Type; got != "sqlite3" {
		t.Fatalf("expected sqlite3 database type in test env, got %q", got)
	}
}

func TestLoadConfig_PanicsForSQLiteOutsideTestEnv(t *testing.T) {
	t.Setenv("APP_ENV", "development")
	t.Setenv("DB_TYPE", "sqlite3")

	defer func() {
		ConfigInstance = nil
		recovered := recover()
		if recovered == nil {
			t.Fatal("expected LoadConfig to panic for sqlite3 outside test env")
		}
	}()

	LoadConfig()
}
