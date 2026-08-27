package routes

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

const delegateOwnershipTestJWTSecret = "delegate-ownership-test-secret-32-chars"

func setupDelegateBotOwnershipRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("JWT_SECRET_KEY", delegateOwnershipTestJWTSecret)
	t.Setenv("APP_ENV", "development")
	t.Setenv("AUTH_RETURN_LEGACY_TOKENS", "false")
	if err := config.LoadConfig(); err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	middleware.InitAuthMiddleware(config.ConfigInstance)

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })

	if _, err := dbConn.Exec(`
	CREATE TABLE bot_instances (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		instance_id TEXT NOT NULL UNIQUE,
		instance_name TEXT,
		user_id INTEGER NOT NULL,
		status TEXT,
		network TEXT,
		strategy TEXT,
		config TEXT,
		trading_params TEXT,
		total_trades INTEGER,
		total_pnl REAL,
		current_balance REAL,
		starting_balance REAL,
		process_id TEXT,
		pid INTEGER,
		host TEXT,
		port INTEGER,
		error_message TEXT,
		last_error_at TIMESTAMP,
		started_at TIMESTAMP,
		stopped_at TIMESTAMP,
		created_at TIMESTAMP NOT NULL,
		updated_at TIMESTAMP NOT NULL
	);`); err != nil {
		t.Fatalf("create bot_instances schema: %v", err)
	}

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, total_trades, created_at, updated_at) VALUES (?, ?, ?, 'running', 'testnet', 'pairs', 0, ?, ?)`,
		"bot-own-1", "owner instance", 7, now, now,
	); err != nil {
		t.Fatalf("seed bot instance: %v", err)
	}

	router := gin.New()
	// Point upstream at an unreachable address: after ownership passes, the
	// delegated call must fail with a transport error, which distinguishes
	// "ownership granted" from "ownership denied (404)".
	unreachableClient := services.NewBotAPIClient("http://127.0.0.1:1", "")
	backtestSync := services.NewBacktestSyncService(repository.NewBacktestSyncRepository(dbConn))
	RegisterBotAPIDelegateRoutesWithSyncAndCache(router, unreachableClient, backtestSync, nil, nil, nil, nil)
	return router, dbConn
}

func delegateOwnershipBearer(t *testing.T, userID int, isAdmin bool) string {
	t.Helper()
	role := "client"
	if isAdmin {
		role = "admin"
	}
	token, err := services.GenerateAccessTokenWithRole(userID, "testuser", isAdmin, role)
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return "Bearer " + token
}

func doDelegateBotRequest(router *gin.Engine, auth string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/api/v1/bots/bot-own-1/positions/current", nil)
	req.Header.Set("Authorization", auth)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	return res
}

// Regression test for the delegated bot-route BOLA: instance-scoped /api/v1/bots
// routes previously proxied to the bot API with no Go-side ownership check, so
// any authenticated user could read another user's live positions.
func TestDelegateBotRoutes_EnforceInstanceOwnership(t *testing.T) {
	router, _ := setupDelegateBotOwnershipRouter(t)

	// Foreign, non-admin user: denied with a non-revealing 404.
	foreign := doDelegateBotRequest(router, delegateOwnershipBearer(t, 8, false))
	if foreign.Code != http.StatusNotFound {
		t.Fatalf("foreign user expected 404, got %d body=%s", foreign.Code, foreign.Body.String())
	}
	var body struct {
		Message string `json:"message"`
	}
	if err := json.Unmarshal(foreign.Body.Bytes(), &body); err == nil && body.Message != "bot instance not found" {
		t.Fatalf("expected bot instance not found, got %q", body.Message)
	}

	// Unknown instance: denied identically.
	req := httptest.NewRequest(http.MethodGet, "/api/v1/bots/does-not-exist/positions/current", nil)
	req.Header.Set("Authorization", delegateOwnershipBearer(t, 7, false))
	unknown := httptest.NewRecorder()
	router.ServeHTTP(unknown, req)
	if unknown.Code != http.StatusNotFound {
		t.Fatalf("unknown instance expected 404, got %d", unknown.Code)
	}

	// Owner: ownership passes; the request proceeds to the (unreachable)
	// upstream and fails there rather than at the authorization gate.
	owner := doDelegateBotRequest(router, delegateOwnershipBearer(t, 7, false))
	if owner.Code == http.StatusNotFound {
		t.Fatalf("owner must pass the ownership gate, got 404 body=%s", owner.Body.String())
	}

	// Admin: bypasses the ownership gate.
	admin := doDelegateBotRequest(router, delegateOwnershipBearer(t, 99, true))
	if admin.Code == http.StatusNotFound {
		t.Fatalf("admin must bypass the ownership gate, got 404 body=%s", admin.Body.String())
	}
}
