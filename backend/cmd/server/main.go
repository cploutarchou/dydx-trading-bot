package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/routes"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
)

func probeJSONEndpoint(url string, timeout time.Duration) (int, map[string]interface{}, string) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return 0, nil, err.Error()
	}

	httpClient := &http.Client{}
	resp, err := httpClient.Do(req)
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

func extractBotRecoveryPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return nil
	}

	if direct, ok := payload["bot_recovery"].(map[string]interface{}); ok {
		return direct
	}

	data, ok := payload["data"].(map[string]interface{})
	if !ok || data == nil {
		return nil
	}

	if nested, ok := data["bot_recovery"].(map[string]interface{}); ok {
		return nested
	}

	return nil
}

func findRepoRoot(start string) string {
	current := filepath.Clean(start)

	for {
		githubPath := filepath.Join(current, ".github")
		agentsPath := filepath.Join(current, "AGENTS.md")
		if info, err := os.Stat(githubPath); err == nil && info.IsDir() {
			if _, err := os.Stat(agentsPath); err == nil {
				configProfilesPath := filepath.Join(current, "config", "profiles")
				if info, err := os.Stat(configProfilesPath); err == nil && info.IsDir() {
					return current
				}
				runConfigPath := filepath.Join(current, "run.json")
				if _, err := os.Stat(runConfigPath); err == nil {
					return current
				}
			}
		}

		parent := filepath.Dir(current)
		if parent == current {
			return ""
		}
		current = parent
	}
}

func loadStructuredConfigEnv() {
	lookupStarts := make([]string, 0, 2)
	if wd, err := os.Getwd(); err == nil && strings.TrimSpace(wd) != "" {
		lookupStarts = append(lookupStarts, wd)
	}
	if execPath, err := os.Executable(); err == nil && strings.TrimSpace(execPath) != "" {
		lookupStarts = append(lookupStarts, filepath.Dir(execPath))
	}

	seen := make(map[string]struct{}, len(lookupStarts))
	for _, start := range lookupStarts {
		repoRoot := findRepoRoot(start)
		if repoRoot == "" {
			continue
		}
		if _, exists := seen[repoRoot]; exists {
			continue
		}
		seen[repoRoot] = struct{}{}

		profilePath, err := config.LoadStructuredConfigEnv(repoRoot, true)
		if err != nil {
			log.Printf("Warning: failed to load structured config from repo root %s: %v", repoRoot, err)
			return
		}

		log.Printf("Loaded structured config from %s", profilePath)
		return
	}

	log.Printf("Warning: structured config not found; using existing process environment variables")
}

func main() {
	startTime := time.Now()
	loadStructuredConfigEnv()

	config.LoadConfig()
	log.Printf("Loaded config (db_type=%s, redis_enabled=%t)", config.ConfigInstance.Database.Type, config.ConfigInstance.Redis.Enabled)
	if err := validateDatabaseOwnership(config.ConfigInstance); err != nil {
		log.Fatalf("Invalid database ownership configuration: %v", err)
	}
	if err := services.ValidateEncryptionKeyConfiguration(); err != nil {
		log.Fatalf("Invalid encryption configuration: %v", err)
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
			log.Printf("Failed to close database: %v", err)
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
		dbOwnership := buildDatabaseOwnershipDiagnostics(config.ConfigInstance)
		dbHealthy := true
		dbError := ""
		if err := database.Health(); err != nil {
			dbHealthy = false
			dbError = err.Error()
		}

		botHealthURL := botAPIURL + "/health"
		botSnapshot, botHealthy := buildDependencySnapshot(botHealthURL)
		var botPayload map[string]interface{}
		if payload, ok := botSnapshot["payload"].(map[string]interface{}); ok {
			botPayload = payload
		}
		botRecovery := extractBotRecoveryPayload(botPayload)
		// Get database stats
		stats := database.GetStats()

		// P2.13: Add operational metrics
		c.JSON(200, gin.H{
			"status":    "healthy",
			"live":      true,
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"dependencies": gin.H{
				"database_healthy": dbHealthy,
				"bot_api_healthy":  botHealthy,
			},
			"database_ownership": dbOwnership,
			"bot_api":            botSnapshot,
			"bot_recovery":       botRecovery,
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
			"service": gin.H{
				"version":        "1.0.0",
				"uptime_seconds": time.Since(startTime).Seconds(),
			},
		})
	})

	// Readiness check endpoint (strict dependency validation for deploy gates).
	router.GET("/ready", func(c *gin.Context) {
		dbOwnership := buildDatabaseOwnershipDiagnostics(config.ConfigInstance)
		if dbOwnership.BlockingViolation {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":             "not_ready",
				"ready":              false,
				"component":          "database_ownership",
				"database_ownership": dbOwnership,
			})
			return
		}

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
		var botPayload map[string]interface{}
		if payload, ok := botSnapshot["payload"].(map[string]interface{}); ok {
			botPayload = payload
		}
		botRecovery := extractBotRecoveryPayload(botPayload)
		if !botReady {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":       "not_ready",
				"ready":        false,
				"component":    "bot_api",
				"bot_api":      botSnapshot,
				"bot_recovery": botRecovery,
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":             "ready",
			"ready":              true,
			"database_ownership": dbOwnership,
			"bot_api":            botSnapshot,
			"bot_recovery":       botRecovery,
			"checked_at_utc":     time.Now().UTC().Format(time.RFC3339),
		})
	})

	// P2.13: Operational metrics endpoint for observability.
	router.GET("/metrics", func(c *gin.Context) {
		stats := database.GetStats()
		botMetricsURL := botAPIURL + "/metrics"
		botSnapshot, _ := buildDependencySnapshot(botMetricsURL)

		c.JSON(200, gin.H{
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
			"uptime_seconds": time.Since(startTime).Seconds(),
			"database": gin.H{
				"connections": gin.H{
					"open":                stats.OpenConnections,
					"in_use":              stats.InUse,
					"idle":                stats.Idle,
					"max_idle_closed":     stats.MaxIdleClosed,
					"max_lifetime_closed": stats.MaxLifetimeClosed,
				},
				"wait_stats": gin.H{
					"count":    stats.WaitCount,
					"duration": stats.WaitDuration.String(),
				},
			},
			"bot_api": botSnapshot,
			"service": gin.H{
				"version":     "1.0.0",
				"environment": os.Getenv("ENVIRONMENT"),
			},
		})
	})

	// Register auth routes (bypasses strict validation)
	routes.RegisterAuthRoutes(router, database.DB)
	routes.RegisterAdminUserRoutes(router, database.DB)
	routes.RegisterPortalRoutes(router, database.DB)
	routes.RegisterIBTierRatesRoutes(router, database.DB)

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
	routes.RegisterMailgunRoutes(router, database)
	routes.RegisterTelegramRoutes(router, database)
	routes.RegisterCodexRoutes(router, database)
	routes.RegisterNewsRoutes(router, database)
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

	// Migration status - protected debug endpoint for confirming seed/data migrations.
	router.GET("/api/v1/debug/migrations/status", middleware.RequireAuth(), func(c *gin.Context) {
		if !c.GetBool("is_admin") {
			c.JSON(http.StatusForbidden, gin.H{"success": false, "message": "Admin access required"})
			return
		}

		var (
			version int64
			dirty   bool
		)

		if err := database.DB.QueryRow(`SELECT version, dirty FROM schema_migrations LIMIT 1`).Scan(&version, &dirty); err != nil {
			if err == sql.ErrNoRows {
				c.JSON(http.StatusOK, gin.H{
					"success": true,
					"message": "No schema migration row found",
					"data": gin.H{
						"migration_version": nil,
						"dirty":             false,
					},
					"timestamp": time.Now().UTC().Format(time.RFC3339),
				})
				return
			}

			c.JSON(http.StatusInternalServerError, gin.H{
				"success": false,
				"message": fmt.Sprintf("Failed to query schema_migrations: %v", err),
			})
			return
		}

		seedPrefixes := []string{"seed_portal_20260411_%", "seed_portal_bulk_20260411_%"}
		usersByPrefix := map[string]int64{}
		applicationsByPrefix := map[string]int64{}
		reviewingByPrefix := map[string]int64{}
		for _, prefix := range seedPrefixes {
			var userCount int64
			_ = database.DB.QueryRow(`SELECT COUNT(*) FROM users WHERE username LIKE $1`, prefix).Scan(&userCount)
			usersByPrefix[prefix] = userCount

			var appCount int64
			_ = database.DB.QueryRow(`
				SELECT COUNT(*)
				FROM partner_applications pa
				LEFT JOIN users u ON u.id = pa.applicant_user_id
				WHERE u.username LIKE $1 OR pa.business_name LIKE REPLACE($1, '%', '') || '%'
			`, prefix).Scan(&appCount)
			applicationsByPrefix[prefix] = appCount

			var reviewingCount int64
			_ = database.DB.QueryRow(`
				SELECT COUNT(*)
				FROM partner_applications pa
				LEFT JOIN users u ON u.id = pa.applicant_user_id
				WHERE pa.status = 'reviewing'
				  AND (u.username LIKE $1 OR pa.business_name LIKE REPLACE($1, '%', '') || '%')
			`, prefix).Scan(&reviewingCount)
			reviewingByPrefix[prefix] = reviewingCount
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Migration and seed status loaded",
			"data": gin.H{
				"migration_version":           version,
				"dirty":                       dirty,
				"seed_users_by_prefix":        usersByPrefix,
				"seed_applications_by_prefix": applicationsByPrefix,
				"seed_reviewing_by_prefix":    reviewingByPrefix,
			},
			"timestamp": time.Now().UTC().Format(time.RFC3339),
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
