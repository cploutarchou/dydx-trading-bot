package config

import (
	"fmt"
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
	switch db.Type {
	case "postgresql", "postgres":
		sslMode := "disable"
		if db.SSL {
			sslMode = "require"
		}
		return "host=" + db.Host + " port=" + strconv.Itoa(db.Port) + " user=" + db.User + " dbname=" + db.Dbname + " password=" + db.Password + " sslmode=" + sslMode + " connect_timeout=" + strconv.Itoa(db.Timeout)
	case "sqlite3", "sqlite":
		return fmt.Sprintf("%s.db", db.Dbname)
	default:
		return "app.db"
	}
}

// MigrationsPath returns the appropriate migrations directory based on database type
func (db *DatabaseSettings) MigrationsPath() string {
	switch db.Type {
	case "postgresql", "postgres":
		return "migrations/postgres"
	case "sqlite3", "sqlite":
		return "migrations/sqlite"
	default:
		return "migrations/sqlite"
	}
}

type RedisSettings struct {
	Host            string
	Port            int
	Db              int
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

func LoadConfig() {
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

	database := DatabaseSettings{
		Host:           getEnvAny([]string{"DB_HOST"}, "localhost"),
		Port:           getEnvIntAny([]string{"DB_PORT", "POSTGRES_PORT"}, 5432),
		Dbname:         getEnvAny([]string{"DB_NAME", "POSTGRES_DB"}, "dydx_bot"),
		User:           getEnvAny([]string{"DB_USER", "POSTGRES_USER"}, "dydx_bot"),
		Type:           getEnv("DB_TYPE", "sqlite3"),
		Password:       getEnvAny([]string{"DB_PASSWORD", "POSTGRES_PASSWORD"}, ""),
		SSL:            getEnvBool("SSL_MODE", false),
		Timeout:        getEnvInt("DB_TIMEOUT", 5),
		MaxConnections: getEnvInt("DB_MAX_CONNECTIONS", 10),
		MaxOverflow:    getEnvInt("DB_MAX_OVERFLOW", 10),
		Enabled:        getEnvBool("DB_ENABLED", true),
		PoolSize:       getEnvInt("DB_POOL_SIZE", 5),
	}

	redis := RedisSettings{
		Host:            getEnv("REDIS_HOST", "localhost"),
		Port:            getEnvIntAny([]string{"REDIS_PORT"}, 6379),
		Db:              getEnvInt("REDIS_DB", 0),
		Password:        os.Getenv("REDIS_PASSWORD"),
		SSL:             getEnvBool("REDIS_SSL", false),
		Timeout:         getEnvInt("REDIS_TIMEOUT", 5),
		CacheTTLSeconds: getEnvIntAny([]string{"REDIS_CACHE_TTL", "REDIS_CACHE_TTL_SECONDS"}, 86400),
		MaxConnections:  getEnvInt("REDIS_MAX_CONNECTIONS", 10),
		Enabled:         getEnvBool("REDIS_ENABLED", true),
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
