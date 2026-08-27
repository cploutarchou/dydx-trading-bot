package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/app"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/dydx-trading-bot/backend-go/internal/startup"
)

func autoMigrateEnabled() (bool, error) {
	raw := strings.ToLower(strings.TrimSpace(os.Getenv("DB_AUTO_MIGRATE")))
	switch raw {
	case "1", "true", "yes", "on":
		return true, nil
	case "", "0", "false", "no", "off":
		return false, nil
	default:
		return false, fmt.Errorf("DB_AUTO_MIGRATE must be a boolean, got %q", raw)
	}
}

func loadStructuredConfigEnv() {
	profilePath, err := config.AutoLoadStructuredConfigEnv(true)
	if err != nil {
		log.Printf("Warning: structured config not found or failed to load: %v; using existing process environment variables", err)
		return
	}
	log.Printf("Loaded structured config from %s", profilePath)
}

func main() {
	startTime := time.Now()
	if err := config.LoadFileEnvValues(true); err != nil {
		log.Fatalf("Failed to load file-backed environment values: %v", err)
	}
	loadStructuredConfigEnv()
	if err := config.LoadFileEnvValues(true); err != nil {
		log.Fatalf("Failed to load file-backed environment values: %v", err)
	}

	if err := config.LoadConfig(); err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}
	log.Printf("Loaded config (db_type=%s, redis_enabled=%t)", config.ConfigInstance.Database.Type, config.ConfigInstance.Redis.Enabled)

	if err := startup.ValidateDatabaseOwnership(config.ConfigInstance); err != nil {
		log.Fatalf("Invalid database ownership configuration: %v", err)
	}
	if err := startup.ValidateSecurityBaseline(config.ConfigInstance); err != nil {
		log.Fatalf("Invalid production security baseline: %v", err)
	}
	if err := services.ValidateEncryptionKeyConfiguration(); err != nil {
		log.Fatalf("Invalid encryption configuration: %v", err)
	}

	autoMigrate, err := autoMigrateEnabled()
	if err != nil {
		log.Fatalf("Invalid migration configuration: %v", err)
	}
	database, err := db.New(db.Config{
		Driver:         config.ConfigInstance.Database.Type,
		DSN:            config.ConfigInstance.Database.DSN(),
		AutoMigrate:    autoMigrate,
		MigrationsPath: config.ConfigInstance.Database.MigrationsPath(),
		MaxOpenConns:   config.ConfigInstance.Database.MaxConnections,
		MaxIdleConns:   config.ConfigInstance.Database.PoolSize,
	})
	if err != nil || database == nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer func() {
		if err := database.Close(); err != nil {
			log.Printf("Failed to close database: %v", err)
		}
	}()

	conn, err := database.GetConnection()
	if err != nil {
		log.Fatalf("Failed to access database connection for bootstrap admin: %v", err)
	}
	if err := startup.EnsureBootstrapAdmin(conn); err != nil {
		log.Fatalf("Failed to ensure bootstrap admin: %v", err)
	}

	middleware.InitAuthMiddleware(config.ConfigInstance)
	if config.ConfigInstance.Auth.JWTSecretKey != "" {
		log.Printf("Auth middleware initialized (JWT secret length=%d)", len(config.ConfigInstance.Auth.JWTSecretKey))
	} else {
		log.Printf("Auth middleware initialized with empty JWT secret")
	}

	// Root lifecycle context: cancelled on SIGTERM/SIGINT so background workers
	// stop and the HTTP server drains in-flight requests before exit.
	rootCtx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	botAPIURL := app.ResolveBotAPIURL()
	router, err := app.BuildRouter(config.ConfigInstance, app.Dependencies{
		Database:     database,
		BotAPIClient: services.NewBotAPIClient(botAPIURL, os.Getenv("BOT_API_TOKEN")),
		BotAPIURL:    botAPIURL,
		StartTime:    startTime,
		RootContext:  rootCtx,
	})
	if err != nil {
		log.Fatalf("Failed to build router: %v", err)
	}

	if err := app.RunServer(rootCtx, router, os.Getenv("API_PORT")); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
