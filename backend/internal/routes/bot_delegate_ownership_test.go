package routes

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
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
	// Pin SECRET_KEY too: constructing a BotAPIClient triggers the structured
	// config auto-load, which persistently exports any *empty* env var from
	// the (now decryptable) dev profile — unpinned secrets would leak into
	// every later test in this package.
	t.Setenv("SECRET_KEY", delegateOwnershipTestJWTSecret)
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
	// Legacy unattributed row (user_id = 0): previously accessible by ANY
	// authenticated user; must now be admin-only.
	if _, err := dbConn.Exec(
		`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, total_trades, created_at, updated_at) VALUES (?, ?, 0, 'running', 'testnet', 'pairs', 0, ?, ?)`,
		"bot-legacy-0", "unattributed instance", now, now,
	); err != nil {
		t.Fatalf("seed legacy bot instance: %v", err)
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

// Unattributed legacy rows (user_id = 0) must be denied for regular users
// (fail closed) and remain reachable for admins.
func TestDelegateBotRoutes_DenyUnattributedLegacyInstances(t *testing.T) {
	router, _ := setupDelegateBotOwnershipRouter(t)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/bots/bot-legacy-0/positions/current", nil)

	req.Header.Set("Authorization", delegateOwnershipBearer(t, 8, false))
	regular := httptest.NewRecorder()
	router.ServeHTTP(regular, req)
	if regular.Code != http.StatusNotFound {
		t.Fatalf("regular user on user_id=0 instance expected 404, got %d body=%s", regular.Code, regular.Body.String())
	}

	adminReq := httptest.NewRequest(http.MethodGet, "/api/v1/bots/bot-legacy-0/positions/current", nil)
	adminReq.Header.Set("Authorization", delegateOwnershipBearer(t, 99, true))
	adminRes := httptest.NewRecorder()
	router.ServeHTTP(adminRes, adminReq)
	if adminRes.Code == http.StatusNotFound {
		t.Fatalf("admin must reach user_id=0 instance past the ownership gate, got 404 body=%s", adminRes.Body.String())
	}
}

// Quick-deploy must enforce the per-user instance quota (audit P1-1): it
// spawns a real auto-started instance upstream and previously bypassed both
// the quota and user attribution entirely.
func TestQuickDeploy_EnforcesUserQuota(t *testing.T) {
	router, dbConn := setupDelegateBotOwnershipRouter(t)

	if _, err := dbConn.Exec(`
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT NOT NULL UNIQUE,
		email TEXT NOT NULL UNIQUE,
		role TEXT NOT NULL DEFAULT 'client',
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		mfa_enabled BOOLEAN NOT NULL DEFAULT 0,
		password_change_required BOOLEAN NOT NULL DEFAULT 0,
		max_bot_instances INTEGER,
		last_login DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create users schema: %v", err)
	}
	// Seed instances until user 7 hits the DEFAULT quota of 10 (the
	// per-user max_bot_instances override relies on schema-column probing
	// that is cached package-wide, so the default quota is the reliable
	// path in tests).
	now := time.Now().UTC()
	for i := 0; i < 10; i++ {
		if _, err := dbConn.Exec(
			`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, total_trades, created_at, updated_at)
			 VALUES (?, ?, 7, 'running', 'testnet', 'pairs', 0, ?, ?)`,
			fmt.Sprintf("bot-quota-%d", i), fmt.Sprintf("quota instance %d", i), now, now,
		); err != nil {
			t.Fatalf("seed quota instance: %v", err)
		}
	}
	// User 7 now owns ten instances (one from setup + nine here) with a
	// default quota of 10: quick-deploy must be rejected with 429.
	req := httptest.NewRequest(http.MethodPost, "/api/v1/bots/quick-deploy?instance_name=over-quota", strings.NewReader("{}"))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", delegateOwnershipBearer(t, 7, false))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusTooManyRequests {
		t.Fatalf("over-quota quick-deploy expected 429, got %d body=%s", res.Code, res.Body.String())
	}

	// A user under quota passes the gate and fails at the (unreachable)
	// upstream instead of at the quota check.
	underReq := httptest.NewRequest(http.MethodPost, "/api/v1/bots/quick-deploy?instance_name=ok", strings.NewReader("{}"))
	underReq.Header.Set("Content-Type", "application/json")
	underReq.Header.Set("Authorization", delegateOwnershipBearer(t, 8, false))
	underRes := httptest.NewRecorder()
	router.ServeHTTP(underRes, underReq)
	if underRes.Code == http.StatusTooManyRequests || underRes.Code == http.StatusUnauthorized {
		t.Fatalf("under-quota quick-deploy must pass the gate, got %d body=%s", underRes.Code, underRes.Body.String())
	}
}
