package routes

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

const backtestListTestJWTSecret = "backtest-list-test-secret-32-chars!!"

func setupBacktestListRouter(t *testing.T) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)

	// The repositories bind placeholders by driver name.
	t.Setenv("DB_TYPE", "sqlite")
	// Pin the secrets the bot client's structured config auto-load could
	// otherwise export into the process environment.
	t.Setenv("JWT_SECRET_KEY", backtestListTestJWTSecret)
	t.Setenv("SECRET_KEY", backtestListTestJWTSecret)
	t.Setenv("BOT_API_TOKEN", "backtest-list-bot-token")
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "false")
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             backtestListTestJWTSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	dbConn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = dbConn.Close() })
	if _, err := dbConn.Exec(`CREATE TABLE backtest_runs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER,
		strategy_id INTEGER,
		strategy_version_id INTEGER,
		run_id TEXT NOT NULL,
		status TEXT,
		start_date TEXT NOT NULL DEFAULT '',
		end_date TEXT NOT NULL DEFAULT '',
		num_pairs INTEGER NOT NULL DEFAULT 0,
		total_markets INTEGER NOT NULL DEFAULT 0,
		resolution TEXT,
		total_trades INTEGER,
		profitable_trades INTEGER,
		losing_trades INTEGER,
		win_rate REAL,
		total_pnl REAL,
		total_pnl_usd REAL,
		sharpe_ratio REAL,
		sortino_ratio REAL,
		calmar_ratio REAL,
		max_drawdown REAL,
		profit_factor REAL,
		starting_balance REAL,
		ending_balance REAL,
		max_balance REAL,
		min_balance REAL,
		error_message TEXT,
		started_at DATETIME,
		completed_at DATETIME,
		duration_seconds REAL,
		config TEXT,
		strategy_snapshot TEXT,
		created_at DATETIME NOT NULL
	)`); err != nil {
		t.Fatalf("create backtest_runs: %v", err)
	}

	base := time.Date(2026, 9, 1, 12, 0, 0, 0, time.UTC)
	rows := []struct {
		user, strategy int
		runID, status  string
	}{
		{7, 1, "s1-completed-a", "completed"},
		{7, 1, "s1-completed-b", "Completed"},
		{7, 1, "s1-running", "running"},
		{7, 2, "s2-completed", "completed"},
		{8, 1, "other-user", "completed"},
	}
	for i, row := range rows {
		if _, err := dbConn.Exec(`INSERT INTO backtest_runs (user_id, strategy_id, run_id, status, total_trades, win_rate, created_at)
			VALUES (?, ?, ?, ?, 10, 55.0, ?)`, row.user, row.strategy, row.runID, row.status, base.Add(time.Duration(i)*time.Minute)); err != nil {
			t.Fatalf("insert run %s: %v", row.runID, err)
		}
	}

	router := gin.New()
	unreachableClient := services.NewBotAPIClient("http://127.0.0.1:1", "")
	backtestSync := services.NewBacktestSyncService(repository.NewBacktestSyncRepository(dbConn))
	RegisterBotAPIDelegateRoutesWithSyncAndCache(router, unreachableClient, backtestSync, nil, nil, nil, nil)
	return router
}

func listBacktests(t *testing.T, router *gin.Engine, query string) (int, map[string]any) {
	t.Helper()
	manager := auth.NewManager(auth.JWTConfig{Secret: backtestListTestJWTSecret, ExpiryHours: 1, RefreshExpiryDays: 7})
	token, _, err := manager.CreateAccessToken(7, "list-user", "list-user@example.local", false)
	if err != nil {
		t.Fatalf("create token: %v", err)
	}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/backtests"+query, nil)
	req.Header.Set("Authorization", "Bearer "+token)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	var envelope map[string]any
	if err := json.Unmarshal(res.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode %q: %v", res.Body.String(), err)
	}
	return res.Code, envelope
}

func listedRunIDs(t *testing.T, envelope map[string]any) []string {
	t.Helper()
	data, _ := envelope["data"].(map[string]any)
	items, _ := data["backtests"].([]any)
	ids := make([]string, 0, len(items))
	for _, item := range items {
		run, _ := item.(map[string]any)
		ids = append(ids, run["run_id"].(string))
	}
	return ids
}

func listedTotal(envelope map[string]any) float64 {
	data, _ := envelope["data"].(map[string]any)
	total, _ := data["total"].(float64)
	return total
}

func TestBacktestListHonoursStrategyAndStatusFilters(t *testing.T) {
	router := setupBacktestListRouter(t)

	status, envelope := listBacktests(t, router, "")
	if status != http.StatusOK || len(listedRunIDs(t, envelope)) != 4 || listedTotal(envelope) != 4 {
		t.Fatalf("expected the caller's four runs without filters, got %d %+v", status, envelope)
	}

	status, envelope = listBacktests(t, router, "?strategy_id=1")
	ids := listedRunIDs(t, envelope)
	if status != http.StatusOK || len(ids) != 3 || listedTotal(envelope) != 3 {
		t.Fatalf("expected three runs of strategy 1, got %d %v total=%v", status, ids, listedTotal(envelope))
	}
	if ids[0] != "s1-running" || ids[2] != "s1-completed-a" {
		t.Fatalf("expected newest first, got %v", ids)
	}
	for _, id := range ids {
		if id == "s2-completed" || id == "other-user" {
			t.Fatalf("expected only the caller's strategy-1 runs, got %v", ids)
		}
	}

	status, envelope = listBacktests(t, router, "?strategy_id=1&status=done,COMPLETED&limit=1")
	ids = listedRunIDs(t, envelope)
	if status != http.StatusOK || len(ids) != 1 || ids[0] != "s1-completed-b" || listedTotal(envelope) != 2 {
		t.Fatalf("expected one page of the two completed strategy-1 runs with total 2, got %d %v total=%v", status, ids, listedTotal(envelope))
	}

	status, envelope = listBacktests(t, router, "?status=completed")
	ids = listedRunIDs(t, envelope)
	if status != http.StatusOK || len(ids) != 3 || listedTotal(envelope) != 3 {
		t.Fatalf("expected the caller's three completed runs across strategies, got %d %v", status, ids)
	}

	status, envelope = listBacktests(t, router, "?strategy_id=1&status=failed")
	if status != http.StatusOK || len(listedRunIDs(t, envelope)) != 0 || listedTotal(envelope) != 0 {
		t.Fatalf("expected no failed runs, got %d %+v", status, envelope)
	}

	status, envelope = listBacktests(t, router, "?strategy_id=abc")
	if status != http.StatusBadRequest || envelope["success"] != false {
		t.Fatalf("expected 400 for a non-numeric strategy_id, got %d %+v", status, envelope)
	}
}

func TestParseBacktestListStatuses(t *testing.T) {
	got := parseBacktestListStatuses(" Done, completed,error,,RUNNING,stalled ")
	want := []string{"completed", "failed", "running", "stale"}
	if len(got) != len(want) {
		t.Fatalf("expected %v, got %v", want, got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("expected %v, got %v", want, got)
		}
	}
	if len(parseBacktestListStatuses("")) != 0 {
		t.Fatal("expected no statuses for an empty filter")
	}
}
