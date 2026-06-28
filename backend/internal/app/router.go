package app

import (
	"context"
	"database/sql"
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
	gzip "github.com/gin-contrib/gzip"
	"github.com/gin-gonic/gin"
)

type Dependencies struct {
	Database        *db.Database
	BotAPIClient    *services.BotAPIClient
	CacheService    *services.CacheService
	BacktestPushHub *services.BacktestPushHub
	BotAPIURL       string
	StartTime       time.Time
}

func ResolveBotAPIURL() string {
	botAPIURL := strings.TrimRight(os.Getenv("BOT_API_URL"), "/")
	if botAPIURL == "" {
		botAPIURL = "http://127.0.0.1:8889"
	}
	return botAPIURL
}

func isWebSocketUpgradeRequest(request *http.Request) bool {
	if request == nil {
		return false
	}

	connectionHeader := strings.ToLower(strings.TrimSpace(request.Header.Get("Connection")))
	upgradeHeader := strings.ToLower(strings.TrimSpace(request.Header.Get("Upgrade")))
	return strings.Contains(connectionHeader, "upgrade") && upgradeHeader == "websocket"
}

func shouldCompressResponse(c *gin.Context) bool {
	if c == nil {
		return true
	}
	return !isWebSocketUpgradeRequest(c.Request)
}

func BuildRouter(cfg *config.Config, deps Dependencies) (*gin.Engine, error) {
	if cfg == nil {
		return nil, fmt.Errorf("config is required")
	}
	if deps.Database == nil || deps.Database.DB == nil {
		return nil, fmt.Errorf("database is required")
	}
	if deps.StartTime.IsZero() {
		deps.StartTime = time.Now()
	}
	if strings.TrimSpace(deps.BotAPIURL) == "" {
		deps.BotAPIURL = ResolveBotAPIURL()
	}
	if deps.BotAPIClient == nil {
		deps.BotAPIClient = services.NewBotAPIClient(deps.BotAPIURL, os.Getenv("BOT_API_TOKEN"))
	}

	router := gin.Default()
	if err := router.SetTrustedProxies([]string{"127.0.0.1", "::1"}); err != nil {
		log.Printf("Warning: failed to set trusted proxies: %v", err)
	}

	router.Use(middleware.RequestTraceMiddleware())
	router.Use(middleware.ErrorHandlingMiddleware())
	router.Use(middleware.CORSMiddleware())
	router.Use(middleware.HeaderLoggingMiddleware())
	router.Use(middleware.RequestLoggingMiddleware())
	router.Use(middleware.RateLimitMiddleware(100, 200))
	router.Use(gzip.Gzip(
		gzip.DefaultCompression,
		gzip.WithExcludedPaths([]string{"/health", "/ready", "/api/v1/health", "/api/v1/ready"}),
		gzip.WithCustomShouldCompressFn(shouldCompressResponse),
	))

	// Build CacheService if Redis is enabled and not explicitly provided
	if deps.CacheService == nil && cfg.Redis.Enabled {
		deps.CacheService = services.NewCacheService(
			cfg.Redis.Host,
			cfg.Redis.Port,
			cfg.Redis.Password,
			cfg.Redis.DB,
		)
	}

	// Build BacktestPushHub if Redis is enabled
	if deps.BacktestPushHub == nil && cfg.Redis.Enabled {
		deps.BacktestPushHub = services.NewBacktestPushHub(
			cfg.Redis.Host,
			cfg.Redis.Port,
			cfg.Redis.Password,
			cfg.Redis.DB,
		)
	}

	registerHealthRoutes(router, cfg, deps.Database, deps.BotAPIURL, deps.StartTime)
	registerFeatureRoutes(router, deps.Database, deps.BotAPIClient, deps.CacheService, deps.BacktestPushHub)
	registerDebugRoutes(router, deps.Database)

	// Backend-owned ClickHouse read models. Each reader is nil when ClickHouse is
	// disabled (the checked-in default), in which case analytics routes fail
	// closed with enabled=false instead of erroring.
	clickHouseReader := services.NewClickHouseReader(cfg.ClickHouse)
	registerAnalyticsRoutes(router,
		services.NewLivePositionReader(clickHouseReader),
		services.NewLiveTradeSummaryReader(clickHouseReader),
		services.NewLivePairBreakdownReader(clickHouseReader),
	)

	return router, nil
}

func registerFeatureRoutes(router *gin.Engine, database *db.Database, apiClient *services.BotAPIClient, cacheService *services.CacheService, backtestPushHub *services.BacktestPushHub) {
	routes.RegisterAuthRoutes(router, database.DB)
	routes.RegisterAdminUserRoutes(router, database.DB)
	routes.RegisterBackofficeRoutes(router, database.DB)
	routes.RegisterPortalRoutes(router, database.DB)
	routes.RegisterIBPortalRoutes(router, database.DB)
	routes.RegisterIBTierRatesRoutes(router, database.DB)
	routes.RegisterSettingsRoutes(router, database)
	routes.RegisterICOPublicRoutes(router, database.DB)
	routes.RegisterICOAdminRoutes(router, database.DB)
	startICOEmailOutboxWorker(database.DB)

	router.Use(middleware.ComingSoonMiddleware(database.DB))

	log.Printf("Initialized bot API client pointing to: %s", apiClient.BaseURL())
	backtestSyncRepo := repository.NewBacktestSyncRepository(database.DB)
	backtestSyncService := services.NewBacktestSyncService(backtestSyncRepo)

	routes.RegisterBotInstanceRoutes(router, database, cacheService)
	routes.RegisterBotAPIDelegateRoutesWithSyncCacheAndPush(router, apiClient, backtestSyncService, cacheService, backtestPushHub)
	routes.RegisterAIMarketRoutes(router, database, apiClient)
	routes.RegisterKeyRoutes(router, database)
	routes.RegisterPairStorageRoutes(router)
	routes.RegisterArbitrageSettingsRoutes(router, database, apiClient)
	routes.RegisterMailgunRoutes(router, database)
	routes.RegisterTelegramRoutes(router, database)
	routes.RegisterCodexRoutes(router, database)
	routes.RegisterNewsRoutes(router, database)
	routes.RegisterStrategyRoutes(router, database)
	routes.RegisterTradeLogRoutes(router, database)
	routes.RegisterAuditLogRoutes(router, database)
}

func startICOEmailOutboxWorker(sqlDB *sql.DB) {
	if strings.EqualFold(strings.TrimSpace(os.Getenv("ICO_EMAIL_OUTBOX_WORKER_ENABLED")), "false") {
		log.Printf("ICO email outbox worker disabled by configuration")
		return
	}
	credentialRepo := repository.NewExternalAPICredentialRepository(sqlDB)
	settingsRepo := repository.NewSettingsRepository(sqlDB)
	userRepo := repository.NewUserRepository(sqlDB)
	credentialService := services.NewExternalAPICredentialService(credentialRepo)
	mailgunService := services.NewMailgunService(credentialService, settingsRepo, userRepo)
	whitelistRepo := repository.NewICOWhitelistRepository(sqlDB)
	outboxService := services.NewICOEmailOutboxService(whitelistRepo, mailgunService)

	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
			if _, err := outboxService.ProcessPending(ctx, 25); err != nil {
				log.Printf("ICO email outbox worker error: %v", err)
			}
			cancel()
			<-ticker.C
		}
	}()
	log.Printf("ICO email outbox worker started")
}

func registerDebugRoutes(router *gin.Engine, database *db.Database) {
	debug := router.Group("/api/v1/debug")
	debug.Use(middleware.RequireAuth())

	debug.GET("/headers", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"headers":  middleware.SanitizeHeaders(c.Request.Header),
			"trace_id": middleware.GetTraceID(c),
		})
	})

	debug.GET("/whoami", func(c *gin.Context) {
		userID, _ := c.Get("user_id")
		username := c.GetString("username")
		email := c.GetString("email")
		isAdmin := c.GetBool("is_admin")
		c.JSON(http.StatusOK, gin.H{
			"user_id":  userID,
			"username": username,
			"email":    email,
			"is_admin": isAdmin,
		})
	})

	debug.GET("/migrations/status", func(c *gin.Context) {
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
			_ = database.DB.QueryRow(`SELECT COUNT(*) FROM users WHERE username LIKE ?`, prefix).Scan(&userCount)
			usersByPrefix[prefix] = userCount

			var appCount int64
			_ = database.DB.QueryRow(`
				SELECT COUNT(*)
				FROM partner_applications pa
				LEFT JOIN users u ON u.id = pa.applicant_user_id
				WHERE u.username LIKE ? OR pa.business_name LIKE REPLACE(?, '%', '') || '%'
			`, prefix).Scan(&appCount)
			applicationsByPrefix[prefix] = appCount

			var reviewingCount int64
			_ = database.DB.QueryRow(`
				SELECT COUNT(*)
				FROM partner_applications pa
				LEFT JOIN users u ON u.id = pa.applicant_user_id
				WHERE pa.status = 'reviewing'
				  AND (u.username LIKE ? OR pa.business_name LIKE REPLACE(?, '%', '') || '%')
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
}

func RunServer(router *gin.Engine, port string) error {
	if strings.TrimSpace(port) == "" {
		port = "8888"
	}

	for _, route := range router.Routes() {
		log.Printf("Registered route: %s %s", route.Method, route.Path)
	}

	log.Printf("Backend server starting on port %s", port)
	return router.Run(fmt.Sprintf(":%s", port))
}
