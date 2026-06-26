// Package config loads and manages application configuration from environment variables.
package config

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
)

var ConfigInstance *Config

type IndexerEndpoint struct {
	Mainnet string
	Testnet string
}

type TelegramSettings struct {
	Token  string
	ChatID string
}

type DYDXTestnetSettings struct {
	Address string
	Secret  string
}

type DYDXMainnetSettings struct {
	Address string
	Secret  string
}

type DYDX struct {
	IsTestnet           bool
	DYDXTestnetSettings DYDXTestnetSettings
	DYDXMainnetSettings DYDXMainnetSettings
}

type LokiSettings struct {
	Enabled  bool
	URL      string
	Username string
	Password string
	TenantID string
	Labels   map[string]string
}

type DatabaseSettings struct {
	Host           string
	Port           int
	Dbname         string
	User           string
	Type           string
	Password       string
	SSL            bool
	Timeout        int
	MaxConnections int
	MaxOverflow    int
	Enabled        bool
	PoolSize       int
}

func (db *DatabaseSettings) DSN() string {
	query := url.Values{}
	if db.SSL {
		query.Set("sslmode", "require")
	} else {
		query.Set("sslmode", "disable")
	}
	if db.Timeout > 0 {
		query.Set("connect_timeout", strconv.Itoa(db.Timeout))
	}
	query.Set("TimeZone", "UTC")

	host := db.Host
	if db.Port > 0 {
		host = fmt.Sprintf("%s:%d", host, db.Port)
	}

	u := url.URL{Scheme: "postgres", Host: host, Path: "/" + db.Dbname}
	if db.User != "" {
		if db.Password != "" {
			u.User = url.UserPassword(db.User, db.Password)
		} else {
			u.User = url.User(db.User)
		}
	}
	u.RawQuery = query.Encode()
	return u.String()
}

// MigrationsPath returns the migrations directory based on database type.
func (db *DatabaseSettings) MigrationsPath() string {
	return "migrations/postgres"
}

type RedisSettings struct {
	Host            string
	Port            int
	DB              int
	Password        string
	SSL             bool
	Timeout         int
	CacheTTLSeconds int
	MaxConnections  int
	Enabled         bool
}

type AuthSettings struct {
	JWTSecretKey             string
	JWTAlgorithm             string
	AccessTokenExpireMinutes int
	RefreshTokenExpireDays   int
}

type Config struct {
	Database DatabaseSettings
	Indexer  IndexerEndpoint
	Telegram TelegramSettings
	DYDX     DYDX
	Loki     LokiSettings
	Redis    RedisSettings
	Auth     AuthSettings
}

func LoadConfig() error {
	// Note: In Go, dotenv loading is typically done in main, but for compatibility, we can assume it's loaded
	// For now, directly use os.Getenv

	indexer := IndexerEndpoint{
		Mainnet: "https://indexer.dydx.trade",
		Testnet: "https://indexer.v4testnet.dydx.exchange",
	}

	telegram := TelegramSettings{
		Token:  getEnvAny([]string{"TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN"}, ""),
		ChatID: getEnvAny([]string{"TELEGRAM_CHAT_ID"}, ""),
	}

	dydx := DYDX{
		IsTestnet: getEnvBool("IS_TESTNET", false),
		DYDXTestnetSettings: DYDXTestnetSettings{
			Address: "",
			Secret:  "",
		},
		DYDXMainnetSettings: DYDXMainnetSettings{
			Address: "",
			Secret:  "",
		},
	}

	loki := LokiSettings{
		Enabled:  getEnvBool("LOKI_ENABLED", false),
		URL:      getEnvAny([]string{"LOKI_PUSH_URL", "LOKI_URL"}, ""),
		Username: os.Getenv("LOKI_USERNAME"),
		Password: os.Getenv("LOKI_PASSWORD"),
		TenantID: os.Getenv("LOKI_TENANT_ID"),
		Labels:   parseLabels(os.Getenv("LOKI_LABELS")),
	}

	dbType := strings.ToLower(getEnv("DB_TYPE", "postgres"))
	if dbType == "postgresql" {
		dbType = "postgres"
	}
	if dbType != "postgres" {
		return fmt.Errorf("unsupported DB_TYPE %q: supported values are postgres and postgresql", dbType)
	}

	database := DatabaseSettings{
		Host:           getEnvAny([]string{"DB_HOST", "POSTGRES_HOST"}, "localhost"),
		Port:           getEnvIntAny([]string{"DB_PORT", "POSTGRES_PORT"}, 5432),
		Dbname:         getEnvAny([]string{"DB_NAME", "POSTGRES_DB"}, "dydx_bot"),
		User:           getEnvAny([]string{"DB_USER", "POSTGRES_USER"}, "dydx_bot"),
		Type:           "postgres",
		Password:       getEnvAny([]string{"DB_PASSWORD", "POSTGRES_PASSWORD"}, "change-me-db-password"),
		SSL:            getEnvBool("SSL_MODE", false),
		Timeout:        getEnvInt("DB_TIMEOUT", 5),
		MaxConnections: getEnvInt("DB_MAX_CONNECTIONS", 10),
		MaxOverflow:    getEnvInt("DB_MAX_OVERFLOW", 10),
		Enabled:        getEnvBool("DB_ENABLED", true),
		PoolSize:       getEnvInt("DB_POOL_SIZE", 5),
	}
	if parsedDatabase, ok, err := parsePostgresDatabaseURL(strings.TrimSpace(os.Getenv("DATABASE_URL")), database); err != nil {
		return err
	} else if ok {
		database = parsedDatabase
	}

	redis := RedisSettings{
		Host:            getEnvAny([]string{"REDIS_HOST", "VALKEY_HOST"}, "localhost"),
		Port:            getEnvIntAny([]string{"REDIS_PORT", "VALKEY_PORT"}, 6379),
		DB:              getEnvInt("REDIS_DB", 0),
		Password:        os.Getenv("REDIS_PASSWORD"),
		SSL:             getEnvBool("REDIS_SSL", false),
		Timeout:         getEnvInt("REDIS_TIMEOUT", 5),
		CacheTTLSeconds: getEnvIntAny([]string{"REDIS_CACHE_TTL", "REDIS_CACHE_TTL_SECONDS"}, 86400),
		MaxConnections:  getEnvInt("REDIS_MAX_CONNECTIONS", 10),
		Enabled:         getEnvBool("REDIS_ENABLED", true),
	}
	if parsedRedis, ok, err := parseRedisURL(getEnvAny([]string{"REDIS_URL", "VALKEY_URL"}, ""), redis); err != nil {
		return err
	} else if ok {
		redis = parsedRedis
	}

	auth := AuthSettings{
		JWTSecretKey:             getEnvAny([]string{"JWT_SECRET_KEY", "SECRET_KEY"}, "your-super-secret-key-change-in-production"),
		JWTAlgorithm:             getEnv("JWT_ALGORITHM", "HS256"),
		AccessTokenExpireMinutes: getEnvInt("ACCESS_TOKEN_EXPIRE_MINUTES", 30),
		RefreshTokenExpireDays:   getEnvInt("REFRESH_TOKEN_EXPIRE_DAYS", 7),
	}

	ConfigInstance = &Config{
		Database: database,
		Indexer:  indexer,
		Telegram: telegram,
		DYDX:     dydx,
		Loki:     loki,
		Redis:    redis,
		Auth:     auth,
	}

	return nil
}

func parsePostgresDatabaseURL(raw string, defaults DatabaseSettings) (DatabaseSettings, bool, error) {
	if strings.TrimSpace(raw) == "" {
		return defaults, false, nil
	}

	parsed, err := url.Parse(raw)
	if err != nil {
		return defaults, false, fmt.Errorf("invalid DATABASE_URL: %w", err)
	}

	switch strings.ToLower(strings.TrimSpace(parsed.Scheme)) {
	case "postgres", "postgresql":
	default:
		return defaults, false, fmt.Errorf("unsupported DATABASE_URL scheme %q", parsed.Scheme)
	}

	if host := strings.TrimSpace(parsed.Hostname()); host != "" {
		defaults.Host = host
	}
	if port := parsed.Port(); port != "" {
		if parsedPort, err := strconv.Atoi(port); err == nil {
			defaults.Port = parsedPort
		}
	}
	if dbName := strings.TrimPrefix(strings.TrimSpace(parsed.Path), "/"); dbName != "" {
		defaults.Dbname = dbName
	}
	if user := parsed.User.Username(); strings.TrimSpace(user) != "" {
		defaults.User = user
	}
	if password, ok := parsed.User.Password(); ok {
		defaults.Password = password
	}
	if sslmode := strings.ToLower(strings.TrimSpace(parsed.Query().Get("sslmode"))); sslmode != "" {
		defaults.SSL = sslmode != "disable"
	}
	if timeoutValue := strings.TrimSpace(parsed.Query().Get("connect_timeout")); timeoutValue != "" {
		if timeout, err := strconv.Atoi(timeoutValue); err == nil {
			defaults.Timeout = timeout
		}
	}

	defaults.Type = "postgres"
	return defaults, true, nil
}

func parseRedisURL(raw string, defaults RedisSettings) (RedisSettings, bool, error) {
	if strings.TrimSpace(raw) == "" {
		return defaults, false, nil
	}

	parsed, err := url.Parse(raw)
	if err != nil {
		return defaults, false, fmt.Errorf("invalid REDIS_URL: %w", err)
	}

	switch strings.ToLower(strings.TrimSpace(parsed.Scheme)) {
	case "redis", "rediss":
	default:
		return defaults, false, fmt.Errorf("unsupported REDIS_URL scheme %q", parsed.Scheme)
	}

	if host := strings.TrimSpace(parsed.Hostname()); host != "" {
		defaults.Host = host
	}
	if port := parsed.Port(); port != "" {
		if parsedPort, err := strconv.Atoi(port); err == nil {
			defaults.Port = parsedPort
		}
	}
	if password, ok := parsed.User.Password(); ok {
		defaults.Password = password
	}
	if parsed.Path != "" && parsed.Path != "/" {
		if dbValue, err := strconv.Atoi(strings.TrimPrefix(parsed.Path, "/")); err == nil {
			defaults.DB = dbValue
		}
	}
	defaults.SSL = strings.EqualFold(parsed.Scheme, "rediss")

	return defaults, true, nil
}

func LoadFileEnvValues(override bool) error {
	for _, item := range os.Environ() {
		key, value, ok := strings.Cut(item, "=")
		if !ok || !strings.HasSuffix(key, "_FILE") {
			continue
		}

		target := strings.TrimSuffix(key, "_FILE")
		path := strings.TrimSpace(value)
		if target == "" || path == "" {
			continue
		}
		if !override && strings.TrimSpace(os.Getenv(target)) != "" {
			continue
		}

		raw, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("read %s from %s: %w", target, path, err)
		}
		if err := os.Setenv(target, strings.TrimRight(string(raw), "\r\n")); err != nil {
			return fmt.Errorf("set %s from %s: %w", target, path, err)
		}
	}
	return nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAny(keys []string, defaultValue string) string {
	for _, key := range keys {
		if value := os.Getenv(key); value != "" {
			return value
		}
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvIntAny(keys []string, defaultValue int) int {
	for _, key := range keys {
		if value := os.Getenv(key); value != "" {
			if intValue, err := strconv.Atoi(value); err == nil {
				return intValue
			}
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}

func parseLabels(labelsStr string) map[string]string {
	labels := make(map[string]string)
	if labelsStr == "" {
		return labels
	}
	for _, label := range strings.Split(labelsStr, ",") {
		if parts := strings.SplitN(label, "=", 2); len(parts) == 2 {
			labels[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	return labels
}
