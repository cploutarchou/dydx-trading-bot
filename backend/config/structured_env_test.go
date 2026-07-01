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
		{"postgres", "postgres"},
		{"postgresql", "postgres"},
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

func TestLoadConfig_UsesPostgresByDefault(t *testing.T) {
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
	if got := ConfigInstance.Database.Type; got != "postgres" {
		t.Fatalf("expected postgres database type, got %q", got)
	}
}

func TestLoadConfig_ParsesDatabaseURL(t *testing.T) {
	t.Setenv("APP_ENV", "test")
	t.Setenv("DATABASE_URL", "postgres://url_user:url_pass@db.example:5433/url_db?sslmode=require&connect_timeout=11")

	defer func() {
		ConfigInstance = nil
	}()

	if err := LoadConfig(); err != nil {
		t.Fatalf("LoadConfig returned error: %v", err)
	}

	if ConfigInstance == nil {
		t.Fatal("expected ConfigInstance to be initialized")
	}

	if got := ConfigInstance.Database.Host; got != "db.example" {
		t.Fatalf("expected DATABASE_URL host, got %q", got)
	}
	if got := ConfigInstance.Database.Port; got != 5433 {
		t.Fatalf("expected DATABASE_URL port 5433, got %d", got)
	}
	if got := ConfigInstance.Database.Dbname; got != "url_db" {
		t.Fatalf("expected DATABASE_URL dbname, got %q", got)
	}
	if got := ConfigInstance.Database.User; got != "url_user" {
		t.Fatalf("expected DATABASE_URL user, got %q", got)
	}
	if got := ConfigInstance.Database.Password; got != "url_pass" {
		t.Fatalf("expected DATABASE_URL password, got %q", got)
	}
	if got := ConfigInstance.Database.Timeout; got != 11 {
		t.Fatalf("expected DATABASE_URL connect_timeout 11, got %d", got)
	}
	if got := ConfigInstance.Database.SSL; !got {
		t.Fatalf("expected DATABASE_URL sslmode=require to enable SSL")
	}
}

func TestLoadConfig_ParsesRedisAndValkeyAliases(t *testing.T) {
	t.Setenv("APP_ENV", "test")
	t.Setenv("VALKEY_HOST", "valkey.local")
	t.Setenv("VALKEY_PORT", "6381")
	t.Setenv("VALKEY_PASSWORD", "alias-pass")
	t.Setenv("REDIS_URL", "rediss://:cachepass@cache.example:6382/4")

	defer func() {
		ConfigInstance = nil
	}()

	if err := LoadConfig(); err != nil {
		t.Fatalf("LoadConfig returned error: %v", err)
	}

	if ConfigInstance == nil {
		t.Fatal("expected ConfigInstance to be initialized")
	}

	if got := ConfigInstance.Redis.Host; got != "cache.example" {
		t.Fatalf("expected REDIS_URL host, got %q", got)
	}
	if got := ConfigInstance.Redis.Port; got != 6382 {
		t.Fatalf("expected REDIS_URL port 6382, got %d", got)
	}
	if got := ConfigInstance.Redis.DB; got != 4 {
		t.Fatalf("expected REDIS_URL db 4, got %d", got)
	}
	if got := ConfigInstance.Redis.Password; got != "cachepass" {
		t.Fatalf("expected REDIS_URL password, got %q", got)
	}
	if got := ConfigInstance.Redis.SSL; !got {
		t.Fatalf("expected rediss URL to enable SSL")
	}
	if got := ConfigInstance.Valkey.Host; got != "cache.example" {
		t.Fatalf("expected Valkey host to mirror resolved redis-compatible host, got %q", got)
	}
	if got := ConfigInstance.Valkey.Password; got != "cachepass" {
		t.Fatalf("expected Valkey password to mirror resolved redis-compatible password, got %q", got)
	}
}

func TestLoadConfig_ParsesPlatformServiceSettings(t *testing.T) {
	t.Setenv("APP_ENV", "test")
	t.Setenv("NATS_ENABLED", "true")
	t.Setenv("NATS_URL", "nats://nats.internal:4222")
	t.Setenv("NATS_MONITORING_URL", "http://nats.internal:8222")
	t.Setenv("NATS_STREAM_PREFIX", "platform")
	t.Setenv("BOT_COMMAND_BUS_ENABLED", "true")
	t.Setenv("CLICKHOUSE_ENABLED", "true")
	t.Setenv("CLICKHOUSE_URL", "http://analytics.internal:8123")
	t.Setenv("CLICKHOUSE_HOST", "analytics.internal")
	t.Setenv("CLICKHOUSE_PORT", "8123")
	t.Setenv("CLICKHOUSE_DATABASE", "dydx_analytics")
	t.Setenv("CLICKHOUSE_USER", "analytics")
	t.Setenv("CLICKHOUSE_PASSWORD", "analytics-pass")
	t.Setenv("MINIO_ENABLED", "true")
	t.Setenv("MINIO_ENDPOINT", "minio.internal:9000")
	t.Setenv("MINIO_CONSOLE_URL", "http://minio.internal:9001")
	t.Setenv("MINIO_BUCKET", "backtest-artifacts")
	t.Setenv("MINIO_ACCESS_KEY", "access-key")
	t.Setenv("MINIO_SECRET_KEY", "secret-key")

	defer func() {
		ConfigInstance = nil
	}()

	if err := LoadConfig(); err != nil {
		t.Fatalf("LoadConfig returned error: %v", err)
	}

	if ConfigInstance == nil {
		t.Fatal("expected ConfigInstance to be initialized")
	}
	if got := ConfigInstance.NATS.URL; got != "nats://nats.internal:4222" {
		t.Fatalf("expected NATS URL, got %q", got)
	}
	if got := ConfigInstance.NATS.StreamPrefix; got != "platform" {
		t.Fatalf("expected NATS stream prefix, got %q", got)
	}
	if got := ConfigInstance.NATS.CommandBusEnabled; !got {
		t.Fatalf("expected command bus flag to be enabled")
	}
	if got := ConfigInstance.ClickHouse.Database; got != "dydx_analytics" {
		t.Fatalf("expected ClickHouse database, got %q", got)
	}
	if got := ConfigInstance.ClickHouse.Password; got != "analytics-pass" {
		t.Fatalf("expected ClickHouse password, got %q", got)
	}
	if got := ConfigInstance.MinIO.Bucket; got != "backtest-artifacts" {
		t.Fatalf("expected MinIO bucket, got %q", got)
	}
	if got := ConfigInstance.MinIO.AccessKey; got != "access-key" {
		t.Fatalf("expected MinIO access key, got %q", got)
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
		Host:    "postgres",
		Port:    5432,
		Dbname:  "dydx_bot",
		User:    "dydx_bot",
		Type:    "postgres",
		Timeout: 5,
	}

	dsn := db.DSN()
	if strings.Contains(dsn, "password") {
		t.Fatalf("expected empty password to be omitted from DSN, got %q", dsn)
	}
	if !strings.Contains(dsn, "sslmode=disable") || !strings.Contains(dsn, "TimeZone=UTC") {
		t.Fatalf("expected postgres DSN options in DSN, got %q", dsn)
	}
	if strings.Contains(dsn, "charset=utf8mb4") {
		t.Fatalf("expected mysql params to be omitted from postgres DSN, got %q", dsn)
	}
}

func TestDatabaseSettingsDSN_EnablesTLSWhenSSLModeEnabled(t *testing.T) {
	db := DatabaseSettings{
		Host:    "postgres",
		Port:    5432,
		Dbname:  "dydx_bot",
		User:    "dydx_bot",
		Type:    "postgres",
		SSL:     true,
		Timeout: 5,
	}

	dsn := db.DSN()
	if !strings.Contains(dsn, "sslmode=require") {
		t.Fatalf("expected sslmode=require in DSN when SSL is enabled, got %q", dsn)
	}
}

func TestDatabaseSettingsDSN_BuildsPostgresURI(t *testing.T) {
	db := DatabaseSettings{
		Host:     "postgres",
		Port:     5432,
		Dbname:   "dydx_bot",
		User:     "dydx_bot",
		Password: "secret",
		Type:     "postgres",
		SSL:      false,
		Timeout:  5,
	}

	dsn := db.DSN()
	if !strings.HasPrefix(dsn, "postgres://dydx_bot:secret@postgres:5432/dydx_bot") {
		t.Fatalf("expected postgres URI prefix, got %q", dsn)
	}
	if !strings.Contains(dsn, "sslmode=disable") || !strings.Contains(dsn, "connect_timeout=5") {
		t.Fatalf("expected postgres URI query parameters, got %q", dsn)
	}
	if strings.Contains(dsn, "charset=utf8mb4") || strings.Contains(dsn, "readTimeout") {
		t.Fatalf("expected postgres DSN to omit MySQL-specific params, got %q", dsn)
	}
}

func TestDatabaseSettingsDSN_UsesPostgresSSLModeWhenEnabled(t *testing.T) {
	db := DatabaseSettings{
		Host:    "postgres",
		Port:    5432,
		Dbname:  "dydx_bot",
		User:    "dydx_bot",
		Type:    "postgresql",
		SSL:     true,
		Timeout: 5,
	}

	dsn := db.DSN()
	if !strings.Contains(dsn, "sslmode=require") {
		t.Fatalf("expected sslmode=require in Postgres DSN, got %q", dsn)
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
