package config

import (
	"os"
	"path/filepath"
	"strings"
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

func TestLoadConfig_SupportedDatabases(t *testing.T) {
	testCases := []struct {
		inputType  string
		expectType string
	}{
		{"mysql", "mysql"},
		{"mariadb", "mysql"}, // mariadb is normalized to mysql
	}

	for _, tc := range testCases {
		t.Run(tc.inputType, func(t *testing.T) {
			t.Setenv("APP_ENV", "test")
			t.Setenv("DB_TYPE", tc.inputType)

			defer func() {
				ConfigInstance = nil
			}()

			if err := LoadConfig(); err != nil {
				t.Fatalf("LoadConfig returned error for %s: %v", tc.inputType, err)
			}

			if ConfigInstance == nil {
				t.Fatal("expected ConfigInstance to be initialized")
			}
			if got := ConfigInstance.Database.Type; got != tc.expectType {
				t.Fatalf("expected %s database type for input %s, got %q", tc.expectType, tc.inputType, got)
			}
		})
	}
}

func TestLoadConfig_UsesMariaDBByDefault(t *testing.T) {
	t.Setenv("APP_ENV", "test")

	defer func() {
		ConfigInstance = nil
	}()

	if err := LoadConfig(); err != nil {
		t.Fatalf("LoadConfig returned error: %v", err)
	}

	if ConfigInstance == nil {
		t.Fatal("expected ConfigInstance to be initialized")
	}
	if got := ConfigInstance.Database.Type; got != "mysql" {
		t.Fatalf("expected mysql database type, got %q", got)
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

func TestDatabaseSettingsDSN_OmitsEmptyPasswordAndDisablesSSL(t *testing.T) {
	db := DatabaseSettings{
		Host:    "mariadb",
		Port:    3306,
		Dbname:  "dydx_bot",
		User:    "dydx_bot",
		Timeout: 5,
	}

	dsn := db.DSN()
	if strings.Contains(dsn, "password") {
		t.Fatalf("expected empty password to be omitted from DSN, got %q", dsn)
	}
	if !strings.Contains(dsn, "charset=utf8mb4") || !strings.Contains(dsn, "parseTime=true") || !strings.Contains(dsn, "loc=UTC") {
		t.Fatalf("expected MariaDB DSN options in DSN, got %q", dsn)
	}
}

func TestLoadFileEnvValues_LoadsMountedSecretFile(t *testing.T) {
	secretPath := filepath.Join(t.TempDir(), "jwt")
	if err := os.WriteFile(secretPath, []byte("mounted-secret\n"), 0o600); err != nil {
		t.Fatalf("write secret: %v", err)
	}

	t.Setenv("JWT_SECRET_KEY_FILE", secretPath)
	t.Setenv("JWT_SECRET_KEY", "")

	if err := LoadFileEnvValues(true); err != nil {
		t.Fatalf("LoadFileEnvValues returned error: %v", err)
	}
	if got := os.Getenv("JWT_SECRET_KEY"); got != "mounted-secret" {
		t.Fatalf("expected mounted secret, got %q", got)
	}
}
