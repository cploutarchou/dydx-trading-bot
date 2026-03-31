package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/routes"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
	_ "github.com/mattn/go-sqlite3"
)

func main() {
	// Load environment variables
	err := godotenv.Load(".env", "backend/.env", "../.env")
	if err != nil {
		log.Printf("Warning: no .env file loaded from default paths; using process environment variables")
	}

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
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	// Defer close to execute at the very end of main
	defer func(database *db.Database) {
		err := database.Close()
		if err != nil {
			log.Fatalf("Failed to close database: %v", err)
		}
	}(database)

	if database == nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}

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
	router.Use(middleware.ErrorHandlingMiddleware())
	router.Use(middleware.CORSMiddleware())
	// Header logging middleware (masks Authorization/Cookie)
	router.Use(middleware.HeaderLoggingMiddleware())
	router.Use(middleware.RequestLoggingMiddleware())

	// Add rate limiting middleware (100 requests/second per IP, burst of 200)
	router.Use(middleware.RateLimitMiddleware(100, 200))

	// Health check endpoint (includes database stats and bot API upstream probe)
	router.GET("/health", func(c *gin.Context) {
		if err := database.Health(); err != nil {
			c.JSON(503, gin.H{
				"status": "unhealthy",
				"error":  err.Error(),
			})
			return
		}

		botAPIURL := strings.TrimRight(os.Getenv("BOT_API_URL"), "/")
		if botAPIURL == "" {
			botAPIURL = "http://127.0.0.1:8889"
		}

		botHealthURL := botAPIURL + "/health"
		botReachable := false
		botStatusCode := 0
		botError := ""

		httpClient := &http.Client{Timeout: 3 * time.Second}
		if resp, err := httpClient.Get(botHealthURL); err != nil {
			botError = err.Error()
		} else {
			botStatusCode = resp.StatusCode
			_ = resp.Body.Close()
			if resp.StatusCode >= 200 && resp.StatusCode < 300 {
				botReachable = true
			}
		}

		// Get database stats
		stats := database.GetStats()
		c.JSON(200, gin.H{
			"status": "healthy",
			"bot_api": gin.H{
				"base_url":      botAPIURL,
				"health_url":    botHealthURL,
				"reachable":     botReachable,
				"status_code":   botStatusCode,
				"error":         botError,
				"checked_at_utc": time.Now().UTC().Format(time.RFC3339),
			},
			"database": gin.H{
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

	// Register auth routes (bypasses strict validation)
	routes.RegisterAuthRoutes(router, database.DB)

	// Initialize bot API client for delegating calls to Python bot API
	botAPIURL := os.Getenv("BOT_API_URL")
	if botAPIURL == "" {
		botAPIURL = "http://127.0.0.1:8889" // Default to local bot API (IPv4 loopback)
	}
	botAPIToken := os.Getenv("BOT_API_TOKEN")
	// Token will typically be obtained via login in the frontend
	apiClient := services.NewBotAPIClient(botAPIURL, botAPIToken)
	log.Printf("Initialized bot API client pointing to: %s", botAPIURL)
	// Register all other routes on main router
	// RegisterBacktestRoutes(router, database)
	// Using bot API delegate routes instead for backtests
	routes.RegisterBotInstanceRoutes(router, database)
	routes.RegisterBotAPIDelegateRoutes(router, apiClient) // Register bot API proxy routes (includes backtests)
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
