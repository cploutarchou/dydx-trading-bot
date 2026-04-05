package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/routes"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
)

func probeJSONEndpoint(url string, timeout time.Duration) (int, map[string]interface{}, string) {
	httpClient := &http.Client{Timeout: timeout}
	resp, err := httpClient.Get(url)
	if err != nil {
		return 0, nil, err.Error()
	}
	defer func() { _ = resp.Body.Close() }()

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		payload = nil
	}

	return resp.StatusCode, payload, ""
}

func loadRootEnv() {
	// Prefer backend-local .env first, then fallback to parent locations.
	candidates := []string{".env", "../.env", "../../.env"}

	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err != nil {
			continue
		}

		if err := godotenv.Load(candidate); err != nil {
			log.Printf("Warning: failed to load env file %s: %v", candidate, err)
			return
		}

		log.Printf("Loaded environment from %s", candidate)
		return
	}

	log.Printf("Warning: repo-root .env not found in expected locations; using process environment variables")
}

func main() {
	// Load environment variables from the repo root only.
	loadRootEnv()

	config.LoadConfig()
	log.Printf("Loaded config (db_type=%s, redis_enabled=%t)", config.ConfigInstance.Database.Type, config.ConfigInstance.Redis.Enabled)

	if config.ConfigInstance.Database.Type == "postgresql" {
		config.ConfigInstance.Database.Type = "postgres"
	}

	// Initialize database with automatic migrations
	database, err := db.New(db.Config{
		Driver:         config.ConfigInstance.Database.Type,
		DSN:            config.ConfigInstance.Database.DSN(),
		AutoMigrate:    true, // Automatically run pending migrations on startup
		MigrationsPath: config.ConfigInstance.Database.MigrationsPath(),
		MaxOpenConns:   25,
		MaxIdleConns:   5,
	})
	if err != nil || database == nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	// Defer close to execute at the very end of main
	defer func(database *db.Database) {
		err := database.Close()
		if err != nil {
			log.Fatalf("Failed to close database: %v", err)
		}
	}(database)

	// Initialize auth middleware with config
	middleware.InitAuthMiddleware(config.ConfigInstance)
	// Log masked secret length to help verify correct env var is loaded
	if config.ConfigInstance.Auth.JWTSecretKey != "" {
		log.Printf("Auth middleware initialized (JWT secret length=%d)", len(config.ConfigInstance.Auth.JWTSecretKey))
	} else {
		log.Printf("Auth middleware initialized with empty JWT secret")
	}

	// Create Gin router
	router := gin.Default()

	// Configure trusted proxies to avoid proxy warning
	// Trust localhost and internal networks for development
	if err := router.SetTrustedProxies([]string{"127.0.0.1", "::1"}); err != nil {
		log.Printf("Warning: failed to set trusted proxies: %v", err)
	}

	// Add middleware in order
	router.Use(middleware.RequestTraceMiddleware())
	router.Use(middleware.ErrorHandlingMiddleware())
	router.Use(middleware.CORSMiddleware())
	// Header logging middleware (masks Authorization/Cookie)
	router.Use(middleware.HeaderLoggingMiddleware())
	router.Use(middleware.RequestLoggingMiddleware())

	// Add rate limiting middleware (100 requests/second per IP, burst of 200)
	router.Use(middleware.RateLimitMiddleware(100, 200))

	botAPIURL := strings.TrimRight(os.Getenv("BOT_API_URL"), "/")
	if botAPIURL == "" {
		botAPIURL = "http://127.0.0.1:8889"
	}

	buildDependencySnapshot := func(endpoint string) (gin.H, bool) {
		statusCode, payload, probeError := probeJSONEndpoint(endpoint, 3*time.Second)
		healthy := probeError == "" && statusCode >= 200 && statusCode < 300
		return gin.H{
			"base_url":       botAPIURL,
			"probe_url":      endpoint,
			"reachable":      healthy,
			"status_code":    statusCode,
			"error":          probeError,
			"payload":        payload,
			"checked_at_utc": time.Now().UTC().Format(time.RFC3339),
		}, healthy
	}

	// Health check endpoint (liveness with dependency visibility).
	router.GET("/health", func(c *gin.Context) {
		dbHealthy := true
		dbError := ""
		if err := database.Health(); err != nil {
			dbHealthy = false
			dbError = err.Error()
		}

		botHealthURL := botAPIURL + "/health"
		botSnapshot, botHealthy := buildDependencySnapshot(botHealthURL)
		// Get database stats
		stats := database.GetStats()
		c.JSON(200, gin.H{
			"status": "healthy",
			"live":   true,
			"dependencies": gin.H{
				"database_healthy": dbHealthy,
				"bot_api_healthy":  botHealthy,
			},
			"bot_api": botSnapshot,
			"database": gin.H{
				"healthy":             dbHealthy,
				"error":               dbError,
				"open_connections":    stats.OpenConnections,
				"in_use":              stats.InUse,
				"idle":                stats.Idle,
				"wait_count":          stats.WaitCount,
				"wait_duration":       stats.WaitDuration.String(),
				"max_idle_closed":     stats.MaxIdleClosed,
				"max_lifetime_closed": stats.MaxLifetimeClosed,
			},
		})
	})

	// Readiness check endpoint (strict dependency validation for deploy gates).
	router.GET("/ready", func(c *gin.Context) {
		if err := database.Health(); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":    "not_ready",
				"ready":     false,
				"component": "database",
				"error":     err.Error(),
			})
			return
		}

		botReadyURL := botAPIURL + "/ready"
		botSnapshot, botReady := buildDependencySnapshot(botReadyURL)
		if !botReady {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":    "not_ready",
				"ready":     false,
				"component": "bot_api",
				"bot_api":   botSnapshot,
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":  "ready",
			"ready":   true,
			"bot_api": botSnapshot,
			"checked_at_utc": time.Now().UTC().Format(time.RFC3339),
		})
	})

	// Register auth routes (bypasses strict validation)
	routes.RegisterAuthRoutes(router, database.DB)

	// Initialize bot API client for delegating calls to Python bot API
	botAPIToken := os.Getenv("BOT_API_TOKEN")
	// Token will typically be obtained via login in the frontend
	apiClient := services.NewBotAPIClient(botAPIURL, botAPIToken)
	log.Printf("Initialized bot API client pointing to: %s", botAPIURL)
	backtestSyncRepo := repository.NewBacktestSyncRepository(database.DB)
	backtestSyncService := services.NewBacktestSyncService(backtestSyncRepo)
	// Register all other routes on main router
	// RegisterBacktestRoutes(router, database)
	// Using bot API delegate routes instead for backtests
	routes.RegisterBotInstanceRoutes(router, database)
	routes.RegisterBotAPIDelegateRoutesWithSync(router, apiClient, backtestSyncService) // Register bot API proxy routes (includes backtests)
	routes.RegisterKeyRoutes(router, database)
	routes.RegisterPairStorageRoutes(router)
	routes.RegisterSettingsRoutes(router, database)
	routes.RegisterStrategyRoutes(router, database)
	routes.RegisterTradeLogRoutes(router, database)
	routes.RegisterAuditLogRoutes(router, database)

	// Debug endpoints
	// Echo request headers - public (useful to see what client sends)
	router.GET("/api/v1/debug/headers", func(c *gin.Context) {
		c.JSON(200, gin.H{"headers": c.Request.Header})
	})

	// Whoami - protected by auth middleware and returns claims stored in context
	router.GET("/api/v1/debug/whoami", middleware.RequireAuth(), func(c *gin.Context) {
		userID, _ := c.Get("user_id")
		username := c.GetString("username")
		email := c.GetString("email")
		isAdmin := c.GetBool("is_admin")
		c.JSON(200, gin.H{
			"user_id":  userID,
			"username": username,
			"email":    email,
			"is_admin": isAdmin,
		})
	})

	// Print registered routes for debugging (method + path)
	for _, r := range router.Routes() {
		log.Printf("Registered route: %s %s", r.Method, r.Path)
	}

	// Start server
	port := os.Getenv("API_PORT")
	if port == "" {
		port = "8888"
	}

	log.Printf("🚀 Backend server starting on port %s", port)
	if err := router.Run(fmt.Sprintf(":%s", port)); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
