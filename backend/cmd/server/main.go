package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"

	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/routes"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/dydx-trading-bot/backend-go/internal/startup"
	"github.com/gin-gonic/gin"
)

var sensitiveAssignmentPattern = regexp.MustCompile(`(?i)(password|passwd|pwd|token|secret|key)=([^\s,;]+)`)
var urlUserInfoPattern = regexp.MustCompile(`([a-z][a-z0-9+.-]*://)[^\s/@]+@`)

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

func redactSensitiveText(value string) string {
	value = urlUserInfoPattern.ReplaceAllString(value, "${1}redacted@")
	return sensitiveAssignmentPattern.ReplaceAllString(value, "${1}=redacted")
}

func isSensitiveDependencyKey(key string) bool {
	key = strings.ToLower(strings.TrimSpace(key))
	return strings.Contains(key, "password") ||
		strings.Contains(key, "passwd") ||
		strings.Contains(key, "token") ||
		strings.Contains(key, "secret") ||
		strings.Contains(key, "api_key") ||
		strings.Contains(key, "apikey") ||
		strings.Contains(key, "dsn") ||
		strings.Contains(key, "database_url")
}

func sanitizeDependencyPayload(value interface{}) interface{} {
	switch typed := value.(type) {
	case map[string]interface{}:
		sanitized := make(map[string]interface{}, len(typed))
		for key, nested := range typed {
			if isSensitiveDependencyKey(key) {
				sanitized[key] = "redacted"
				continue
			}
			sanitized[key] = sanitizeDependencyPayload(nested)
		}
		return sanitized
	case []interface{}:
		sanitized := make([]interface{}, 0, len(typed))
		for _, nested := range typed {
			sanitized = append(sanitized, sanitizeDependencyPayload(nested))
		}
		return sanitized
	case string:
		return redactSensitiveText(typed)
	default:
		return value
	}
}

func sanitizeDependencyURL(raw string) string {
	parsed, err := url.Parse(raw)
	if err != nil {
		return redactSensitiveText(raw)
	}
	parsed.User = nil
	query := parsed.Query()
	for key := range query {
		if isSensitiveDependencyKey(key) {
			query.Set(key, "redacted")
		}
	}
	parsed.RawQuery = query.Encode()
	return parsed.String()
}

func buildDependencySnapshot(baseURL, endpoint string, timeout time.Duration) (gin.H, bool) {
	statusCode, payload, probeError := probeJSONEndpoint(endpoint, timeout)
	healthy := probeError == "" && statusCode >= 200 && statusCode < 300

	var sanitizedPayload interface{}
	if payload != nil {
		sanitizedPayload = sanitizeDependencyPayload(payload)
	}

	return gin.H{
		"base_url":       sanitizeDependencyURL(baseURL),
		"probe_url":      sanitizeDependencyURL(endpoint),
		"reachable":      healthy,
		"status_code":    statusCode,
		"error":          redactSensitiveText(probeError),
		"payload":        sanitizedPayload,
		"checked_at_utc": time.Now().UTC().Format(time.RFC3339),
	}, healthy
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

func getPayloadString(payload map[string]interface{}, keys ...string) string {
	for _, key := range keys {
		value, ok := payload[key]
		if !ok || value == nil {
			continue
		}
		switch typed := value.(type) {
		case string:
			if trimmed := strings.TrimSpace(typed); trimmed != "" {
				return redactSensitiveText(trimmed)
			}
		default:
			if trimmed := strings.TrimSpace(fmt.Sprintf("%v", typed)); trimmed != "" && trimmed != "<nil>" {
				return redactSensitiveText(trimmed)
			}
		}
	}
	return ""
}

func appendPayloadBlockers(blockers []string, value interface{}) []string {
	switch typed := value.(type) {
	case []interface{}:
		for _, item := range typed {
			if text := redactSensitiveText(strings.TrimSpace(fmt.Sprintf("%v", item))); text != "" && text != "<nil>" {
				blockers = append(blockers, text)
			}
		}
	case []string:
		for _, item := range typed {
			if text := redactSensitiveText(strings.TrimSpace(item)); text != "" {
				blockers = append(blockers, text)
			}
		}
	case string:
		if text := redactSensitiveText(strings.TrimSpace(typed)); text != "" {
			blockers = append(blockers, text)
		}
	}
	return blockers
}

func buildBotReadinessSummary(snapshot gin.H) gin.H {
	statusCode, _ := snapshot["status_code"].(int)
	probeError, _ := snapshot["error"].(string)
	payload, _ := snapshot["payload"].(map[string]interface{})
	data := map[string]interface{}{}
	if payload != nil {
		if nested, ok := payload["data"].(map[string]interface{}); ok {
			data = nested
		}
	}

	message := getPayloadString(payload, "message", "error", "detail")
	if message == "" {
		message = getPayloadString(data, "message", "error", "detail")
	}
	if message == "" {
		message = strings.TrimSpace(probeError)
	}
	if message == "" && statusCode > 0 {
		message = fmt.Sprintf("upstream bot API readiness check returned HTTP %d", statusCode)
	}
	if message == "" {
		message = "upstream bot API readiness check failed"
	}

	blockers := []string{}
	if payload != nil {
		blockers = appendPayloadBlockers(blockers, payload["blockers"])
		blockers = appendPayloadBlockers(blockers, payload["errors"])
	}
	if data != nil {
		blockers = appendPayloadBlockers(blockers, data["blockers"])
		blockers = appendPayloadBlockers(blockers, data["errors"])
	}
	if len(blockers) == 0 {
		blockers = append(blockers, message)
	}

	reasonText := strings.ToLower(strings.Join(append(blockers, message), " "))
	reason := "bot_api_not_ready"
	action := "check the upstream bot API /ready endpoint and bot service logs"
	if strings.Contains(reasonText, "migration") || strings.Contains(reasonText, "schema") {
		reason = "bot_migrations_unhealthy"
		action = "run or repair the bot service database migrations before marking the backend ready"
	} else if strings.Contains(reasonText, "database") ||
		strings.Contains(reasonText, "db") ||
		strings.Contains(reasonText, "postgres") ||
		strings.Contains(reasonText, "connection refused") ||
		strings.Contains(reasonText, "connect") {
		reason = "bot_database_unavailable"
		action = "verify the dedicated bot database is reachable and the bot service has valid DB configuration"
	} else if strings.TrimSpace(probeError) != "" {
		reason = "bot_api_unreachable"
		action = "ensure the bot service is running and reachable from the backend"
	}

	return gin.H{
		"ready":       false,
		"status_code": statusCode,
		"reason":      reason,
		"message":     message,
		"blockers":    blockers,
		"action":      action,
	}
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

	if err := config.LoadConfig(); err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}
	log.Printf("Loaded config (db_type=%s, redis_enabled=%t)", config.ConfigInstance.Database.Type, config.ConfigInstance.Redis.Enabled)
	if err := startup.ValidateDatabaseOwnership(config.ConfigInstance); err != nil {
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

	// Health check endpoint (liveness with dependency visibility).
	router.GET("/health", func(c *gin.Context) {
		dbOwnership := startup.BuildDatabaseOwnershipDiagnostics(config.ConfigInstance)
		dbHealthy := true
		dbError := ""
		if err := database.Health(); err != nil {
			dbHealthy = false
			dbError = err.Error()
		}

		botHealthURL := botAPIURL + "/health"
		botSnapshot, botHealthy := buildDependencySnapshot(botAPIURL, botHealthURL, 3*time.Second)
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
		dbOwnership := startup.BuildDatabaseOwnershipDiagnostics(config.ConfigInstance)
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
		botSnapshot, botReady := buildDependencySnapshot(botAPIURL, botReadyURL, 3*time.Second)
		var botPayload map[string]interface{}
		if payload, ok := botSnapshot["payload"].(map[string]interface{}); ok {
			botPayload = payload
		}
		botRecovery := extractBotRecoveryPayload(botPayload)
		if !botReady {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":        "not_ready",
				"ready":         false,
				"component":     "bot_api",
				"bot_api":       botSnapshot,
				"bot_recovery":  botRecovery,
				"bot_readiness": buildBotReadinessSummary(botSnapshot),
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
		botSnapshot, _ := buildDependencySnapshot(botAPIURL, botMetricsURL, 3*time.Second)

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
	routes.RegisterAIMarketRoutes(router, database, apiClient)
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
		c.JSON(http.StatusOK, gin.H{
			"headers":  middleware.SanitizeHeaders(c.Request.Header),
			"trace_id": middleware.GetTraceID(c),
		})
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
