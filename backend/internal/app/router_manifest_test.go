package app

import (
	"database/sql"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func TestBuildRouterRegistersCriticalCompatibilityRoutes(t *testing.T) {
	gin.SetMode(gin.TestMode)
	cfg := &config.Config{}
	cfg.Auth.JWTSecretKey = "route-manifest-test-secret"
	cfg.Auth.AccessTokenExpireMinutes = 30
	cfg.Auth.RefreshTokenExpireDays = 7
	cfg.Redis.Enabled = false
	middleware.InitAuthMiddleware(cfg)

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })

	router, err := BuildRouter(cfg, Dependencies{
		Database:     &db.Database{DB: dbConn},
		BotAPIURL:    "http://127.0.0.1:8889",
		BotAPIClient: services.NewBotAPIClient("http://127.0.0.1:8889", ""),
		StartTime:    time.Now(),
	})
	if err != nil {
		t.Fatalf("BuildRouter returned error: %v", err)
	}

	routes := map[string]struct{}{}
	for _, route := range router.Routes() {
		routes[route.Method+" "+route.Path] = struct{}{}
	}

	expected := []string{
		"GET /health",
		"GET /ready",
		"GET /metrics",
		"POST /api/v1/auth/login",
		"GET /api/v1/auth/session",
		"GET /api/v1/public/app-config",
		"GET /api/v1/me",
		"GET /api/v1/backtests",
		"POST /api/v1/backtests/run",
		"GET /api/v1/backtests/:run_id/status",
		"POST /api/v1/backtests/:run_id/resync",
		"GET /api/v1/backtests/sync-health",
		"GET /api/v1/bots/:instance_id/jobs",
		"GET /api/v1/system/status",
		"GET /ws/strategies",
		"GET /api/v1/debug/headers",
		"GET /api/v1/debug/migrations/status",
	}
	for _, key := range expected {
		if _, ok := routes[key]; !ok {
			t.Fatalf("critical route %s was not registered", key)
		}
	}
}
