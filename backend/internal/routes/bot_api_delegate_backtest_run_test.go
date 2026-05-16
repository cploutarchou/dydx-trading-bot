//go:build integration

package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupDelegatedBacktestAuthRouter(t *testing.T, upstream http.Handler) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	const secret = "delegated-backtest-run-test-secret"
	t.Setenv("JWT_SECRET_KEY", secret)
	t.Setenv("APP_ENV", "test")
	t.Setenv("BOT_API_TOKEN", "")
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "false")

	dsn := fmt.Sprintf("file:%d?mode=memory&cache=shared", time.Now().UTC().UnixNano())
	dbConn, err := sql.Open("sqlite", dsn)
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT NOT NULL UNIQUE,
		email TEXT NOT NULL UNIQUE,
		role TEXT NOT NULL DEFAULT 'client',
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		password_change_required BOOLEAN NOT NULL DEFAULT 0,
		last_login DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create users table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE backtest_strategies (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		name TEXT NOT NULL,
		description TEXT,
		category TEXT,
		is_public BOOLEAN NOT NULL DEFAULT 0,
		is_default BOOLEAN NOT NULL DEFAULT 0,
		runtime_strategy TEXT NOT NULL DEFAULT 'cointegration',
		pair_selection_mode TEXT NOT NULL DEFAULT 'liquidity',
		runtime_network TEXT NOT NULL DEFAULT 'testnet',
		runtime_subaccount INTEGER NOT NULL DEFAULT 0,
		selected_markets TEXT NOT NULL DEFAULT '[]',
		zscore_threshold REAL NOT NULL DEFAULT 1.5,
		stats_window INTEGER NOT NULL DEFAULT 21,
		max_half_life REAL NOT NULL DEFAULT 24,
		usd_per_trade REAL NOT NULL DEFAULT 10,
		usd_min_collateral REAL NOT NULL DEFAULT 100,
		close_at_zscore_cross BOOLEAN NOT NULL DEFAULT 1,
		find_cointegrated_pairs BOOLEAN NOT NULL DEFAULT 1,
		manage_exits BOOLEAN NOT NULL DEFAULT 1,
		place_trades BOOLEAN NOT NULL DEFAULT 1,
		abort_all_positions BOOLEAN NOT NULL DEFAULT 0,
		max_positions INTEGER NOT NULL DEFAULT 5,
		max_drawdown_pct REAL NOT NULL DEFAULT 15,
		stop_loss_pct REAL NOT NULL DEFAULT 2,
		take_profit_pct REAL NOT NULL DEFAULT 5,
		trailing_stop_pct REAL NOT NULL DEFAULT 1,
		rebalance_interval_hours INTEGER NOT NULL DEFAULT 24,
		position_timeout_hours INTEGER NOT NULL DEFAULT 72,
		transaction_fee REAL NOT NULL DEFAULT 0.0005,
		slippage REAL NOT NULL DEFAULT 0.001,
		starting_balance REAL NOT NULL DEFAULT 1000,
		candle_resolution TEXT NOT NULL DEFAULT '1HOUR',
		max_history_days INTEGER NOT NULL DEFAULT 90,
		benchmark_symbol TEXT NOT NULL DEFAULT 'BTC-USD',
		risk_free_rate REAL NOT NULL DEFAULT 0.02,
		initial_amount REAL NOT NULL DEFAULT 1000,
		usage_count INTEGER NOT NULL DEFAULT 0,
		last_used_at DATETIME,
		deleted_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create backtest_strategies table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE backtest_runs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		run_id TEXT NOT NULL UNIQUE,
		status TEXT,
		created_at DATETIME,
		started_at DATETIME,
		completed_at DATETIME,
		duration_seconds REAL,
		start_date TEXT NOT NULL,
		end_date TEXT NOT NULL,
		num_pairs INTEGER NOT NULL,
		total_markets INTEGER NOT NULL,
		resolution TEXT,
		config TEXT,
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
		strategy_id INTEGER,
		strategy_version_id INTEGER,
		user_id INTEGER
	);`); err != nil {
		t.Fatalf("create backtest_runs table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE backtest_trades (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		run_id_fk INTEGER NOT NULL,
		trade_id TEXT NOT NULL UNIQUE,
		market_1 TEXT NOT NULL,
		market_2 TEXT NOT NULL,
		entry_timestamp DATETIME NOT NULL,
		entry_price_1 REAL NOT NULL,
		entry_price_2 REAL NOT NULL,
		entry_z_score REAL NOT NULL,
		side_1 TEXT NOT NULL,
		side_2 TEXT NOT NULL,
		size_1 REAL NOT NULL,
		size_2 REAL NOT NULL,
		exit_timestamp DATETIME,
		exit_price_1 REAL,
		exit_price_2 REAL,
		exit_z_score REAL,
		pnl REAL,
		pnl_pct REAL,
		duration_hours REAL,
		hedge_ratio REAL NOT NULL,
		transaction_fee REAL NOT NULL,
		slippage REAL NOT NULL
	);`); err != nil {
		t.Fatalf("create backtest_trades table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE backtest_positions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		run_id_fk INTEGER NOT NULL,
		position_id TEXT NOT NULL UNIQUE,
		market_1 TEXT NOT NULL,
		market_2 TEXT NOT NULL,
		status TEXT NOT NULL,
		entry_timestamp DATETIME NOT NULL,
		close_timestamp DATETIME,
		entry_price_1 REAL NOT NULL,
		entry_price_2 REAL NOT NULL,
		entry_z_score REAL NOT NULL,
		current_price_1 REAL,
		current_price_2 REAL,
		current_z_score REAL,
		size_1 REAL NOT NULL,
		size_2 REAL NOT NULL,
		side_1 TEXT NOT NULL,
		side_2 TEXT NOT NULL,
		hedge_ratio REAL NOT NULL,
		unrealized_pnl REAL,
		realized_pnl REAL
	);`); err != nil {
		t.Fatalf("create backtest_positions table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE backtest_candles (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		run_id_fk INTEGER NOT NULL,
		market TEXT NOT NULL,
		timestamp DATETIME NOT NULL,
		resolution TEXT,
		open_price REAL NOT NULL,
		high_price REAL NOT NULL,
		low_price REAL NOT NULL,
		close_price REAL NOT NULL,
		volume REAL NOT NULL,
		trades_count INTEGER,
		created_at DATETIME
	);`); err != nil {
		t.Fatalf("create backtest_candles table: %v", err)
	}

	hash, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate password hash: %v", err)
	}

	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"smoke-user",
		"smoke-user@example.local",
		"Smoke User",
		"",
		string(hash),
		true,
		false,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert smoke user: %v", err)
	}

	if err := config.LoadConfig(); err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	middleware.InitAuthMiddleware(config.ConfigInstance)

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	upstreamServer := httptest.NewServer(upstream)
	t.Cleanup(upstreamServer.Close)
	RegisterBotAPIDelegateRoutes(router, services.NewBotAPIClient(upstreamServer.URL, ""))

	return router, dbConn
}

func setupDelegatedBacktestAuthRouterWithSync(t *testing.T, upstream http.Handler) (*gin.Engine, *sql.DB) {
	t.Helper()

	_, dbConn := setupDelegatedBacktestAuthRouter(t, upstream)
	upstreamServer := httptest.NewServer(upstream)
	t.Cleanup(upstreamServer.Close)

	apiClient := services.NewBotAPIClient(upstreamServer.URL, "")
	backtestSyncRepo := repository.NewBacktestSyncRepository(dbConn)
	backtestSyncService := services.NewBacktestSyncService(backtestSyncRepo)

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	RegisterBotAPIDelegateRoutesWithSync(router, apiClient, backtestSyncService)

	return router, dbConn
}

func loginDelegatedBacktestTestUser(t *testing.T, backendURL string) string {
	t.Helper()

	loginBody, _ := json.Marshal(map[string]string{
		"username": "smoke-user",
		"password": "Pass123!",
	})
	loginResp, err := http.Post(
		fmt.Sprintf("%s/api/v1/auth/login", backendURL),
		"application/json",
		bytes.NewReader(loginBody),
	)
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = loginResp.Body.Close() }()

	if loginResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected login status: %d", loginResp.StatusCode)
	}

	var tokenResp struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(loginResp.Body).Decode(&tokenResp); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	if tokenResp.AccessToken == "" {
		t.Fatal("missing access token")
	}

	return tokenResp.AccessToken
}

func validDelegatedBacktestRunBody(t *testing.T) []byte {
	t.Helper()
	body, err := json.Marshal(map[string]interface{}{
		"strategy":                  "pairs",
		"pairs":                     []string{"BTC-USD", "ETH-USD"},
		"strategy_payload_snapshot": map[string]interface{}{"strategy": "pairs"},
	})
	if err != nil {
		t.Fatalf("marshal delegated backtest body: %v", err)
	}
	return body
}

func TestDelegatedBacktestRoutes_EnforceUserScopedBacktestData(t *testing.T) {
	upstreamStatusCalls := make(chan string, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests", func(w http.ResponseWriter, _ *http.Request) {
		t.Fatalf("scoped list must not call upstream global backtest list")
	})
	upstreamMux.HandleFunc("/api/v1/backtests/owned-run/status", func(w http.ResponseWriter, _ *http.Request) {
		upstreamStatusCalls <- "owned-run"
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"owned-run","status":"running","progress":42}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/foreign-run/status", func(w http.ResponseWriter, _ *http.Request) {
		t.Fatalf("foreign run must be blocked before upstream status call")
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, total_pnl, total_pnl_usd, user_id)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"owned-run", "completed", now, "2026-04-01", "2026-04-02", 2, 10, 123.45, 123.45, 1,
	); err != nil {
		t.Fatalf("insert owned run: %v", err)
	}
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, total_pnl, total_pnl_usd, user_id)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"foreign-run", "completed", now.Add(-time.Minute), "2026-04-01", "2026-04-02", 2, 10, 999.99, 999.99, 42,
	); err != nil {
		t.Fatalf("insert foreign run: %v", err)
	}

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginDelegatedBacktestTestUser(t, backendServer.URL)

	listReq, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests?limit=50", nil)
	if err != nil {
		t.Fatalf("new list request: %v", err)
	}
	listReq.Header.Set("Authorization", "Bearer "+token)
	listResp, err := http.DefaultClient.Do(listReq)
	if err != nil {
		t.Fatalf("list scoped backtests: %v", err)
	}
	defer func() { _ = listResp.Body.Close() }()
	var listPayload map[string]interface{}
	if err := json.NewDecoder(listResp.Body).Decode(&listPayload); err != nil {
		t.Fatalf("decode list response: %v", err)
	}
	if listResp.StatusCode != http.StatusOK {
		t.Fatalf("expected list 200, got %d: %v", listResp.StatusCode, listPayload)
	}
	listData := assertSuccessEnvelope(t, listPayload)
	backtests, ok := listData["backtests"].([]interface{})
	if !ok {
		t.Fatalf("expected backtests array, got %T", listData["backtests"])
	}
	if len(backtests) != 1 {
		t.Fatalf("expected exactly one owned run, got %d: %v", len(backtests), backtests)
	}
	first, ok := backtests[0].(map[string]interface{})
	if !ok || first["run_id"] != "owned-run" {
		t.Fatalf("expected owned-run only, got %v", backtests[0])
	}

	foreignReq, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/foreign-run/status", nil)
	if err != nil {
		t.Fatalf("new foreign status request: %v", err)
	}
	foreignReq.Header.Set("Authorization", "Bearer "+token)
	foreignResp, err := http.DefaultClient.Do(foreignReq)
	if err != nil {
		t.Fatalf("foreign status request: %v", err)
	}
	defer func() { _ = foreignResp.Body.Close() }()
	if foreignResp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected foreign status 404, got %d", foreignResp.StatusCode)
	}

	ownedReq, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/owned-run/status", nil)
	if err != nil {
		t.Fatalf("new owned status request: %v", err)
	}
	ownedReq.Header.Set("Authorization", "Bearer "+token)
	ownedResp, err := http.DefaultClient.Do(ownedReq)
	if err != nil {
		t.Fatalf("owned status request: %v", err)
	}
	defer func() { _ = ownedResp.Body.Close() }()
	if ownedResp.StatusCode != http.StatusOK {
		t.Fatalf("expected owned status 200, got %d", ownedResp.StatusCode)
	}
	select {
	case got := <-upstreamStatusCalls:
		if got != "owned-run" {
			t.Fatalf("unexpected upstream run id %q", got)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for owned upstream status call")
	}
}

func TestDelegatedBacktestRoutes_EnforceUserScopedBacktestWS(t *testing.T) {
	upgrader := websocket.Upgrader{CheckOrigin: func(_ *http.Request) bool { return true }}
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/ws/backtests/owned-run", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer func() { _ = conn.Close() }()
		payload, _ := json.Marshal(map[string]interface{}{
			"run_id":   "owned-run",
			"status":   "running",
			"progress": 55,
		})
		_ = conn.WriteMessage(websocket.TextMessage, payload)
		time.Sleep(100 * time.Millisecond)
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, total_pnl, total_pnl_usd, user_id)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"owned-run", "running", now, "2026-04-01", "2026-04-02", 2, 10, 0, 0, 1,
	); err != nil {
		t.Fatalf("insert owned run: %v", err)
	}
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, total_pnl, total_pnl_usd, user_id)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"foreign-run", "running", now.Add(-time.Minute), "2026-04-01", "2026-04-02", 2, 10, 0, 0, 42,
	); err != nil {
		t.Fatalf("insert foreign run: %v", err)
	}

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginDelegatedBacktestTestUser(t, backendServer.URL)

	wsHeaders := http.Header{}
	wsHeaders.Set("Authorization", "Bearer "+token)

	foreignWSURL := "ws" + backendServer.URL[len("http"):] + "/ws/backtests/foreign-run"
	_, resp, err := websocket.DefaultDialer.Dial(foreignWSURL, wsHeaders)
	if err == nil {
		t.Fatal("expected websocket dial for foreign run to fail")
	}
	if resp == nil {
		t.Fatal("expected HTTP response for failed foreign websocket dial")
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 for foreign websocket access, got %d", resp.StatusCode)
	}

	ownedWSURL := "ws" + backendServer.URL[len("http"):] + "/ws/backtests/owned-run"
	ownedConn, ownedResp, err := websocket.DefaultDialer.Dial(ownedWSURL, wsHeaders)
	if ownedResp != nil && ownedResp.Body != nil {
		defer func() { _ = ownedResp.Body.Close() }()
	}
	if err != nil {
		t.Fatalf("expected owned websocket dial success, got error: %v", err)
	}
	defer func() { _ = ownedConn.Close() }()

	_, msg, err := ownedConn.ReadMessage()
	if err != nil {
		t.Fatalf("read owned websocket payload: %v", err)
	}
	var payload map[string]interface{}
	if err := json.Unmarshal(msg, &payload); err != nil {
		t.Fatalf("decode owned websocket payload: %v", err)
	}
	if payload["run_id"] != "owned-run" {
		t.Fatalf("unexpected owned websocket payload: %v", payload)
	}
}

func TestDelegatedBacktestRun_UsesCompatibilityRunEndpoint(t *testing.T) {
	upstreamAuthHeaderCh := make(chan string, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"compat-run","status":"queued"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests", func(w http.ResponseWriter, _ *http.Request) {
		t.Fatalf("backend should not call /api/v1/backtests for /run compatibility route")
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_strategies (
			id, user_id, name, description, category, is_public, is_default, runtime_strategy, pair_selection_mode,
			runtime_network, runtime_subaccount, selected_markets, zscore_threshold, stats_window, max_half_life,
			usd_per_trade, usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs, manage_exits,
			place_trades, abort_all_positions, max_positions, max_drawdown_pct, stop_loss_pct, take_profit_pct,
			trailing_stop_pct, rebalance_interval_hours, position_timeout_hours, transaction_fee, slippage,
			starting_balance, candle_resolution, max_history_days, benchmark_symbol, risk_free_rate, initial_amount,
			usage_count, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		77, 1, "Pair Label Strategy", "payload propagation", "pairs", false, false, "cointegration", "input",
		"testnet", 0, `["BTC-USD","ETH-USD","SOL-USD"]`, 1.4, 21, 18.0,
		20.0, 200.0, true, true, true,
		true, false, 5, 10.0, 2.0, 4.0,
		0.8, 24, 72, 0.0005, 0.001,
		1500.0, "1HOUR", 90, "BTC-USD", 0.02, 1500.0,
		0, now, now,
	); err != nil {
		t.Fatalf("insert strategy row: %v", err)
	}

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"strategy":                  "pairs",
		"pairs":                     []string{"BTC-USD", "ETH-USD"},
		"strategy_payload_snapshot": map[string]interface{}{"strategy": "pairs"},
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	select {
	case authHeader := <-upstreamAuthHeaderCh:
		if authHeader == "" {
			t.Fatal("upstream request missing Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream auth header")
	}
}

func TestDelegatedBacktestRun_PassthroughsUpstreamStatus(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = w.Write([]byte(`{"error":"invalid backtest payload"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if got["error"] != "invalid backtest payload" {
		t.Fatalf("unexpected response body: %v", got)
	}
}

func TestDelegatedBacktestRun_ForwardsCookieAliasTokenUpstream(t *testing.T) {
	upstreamAuthHeaderCh := make(chan string, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"cookie-run","status":"queued"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(&http.Cookie{Name: "token", Value: token})

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	select {
	case authHeader := <-upstreamAuthHeaderCh:
		if authHeader != "Bearer "+token {
			t.Fatalf("unexpected upstream auth header: %q", authHeader)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream auth header")
	}
}

func TestDelegatedBacktestRunRejectsMissingSelectedPairs(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		t.Fatal("backend should reject missing selected pairs before delegating")
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"strategy_payload_snapshot": map[string]interface{}{"strategy": "pairs"},
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if got["error"] != "SELECTED_PAIRS_MISSING" {
		t.Fatalf("unexpected response body: %v", got)
	}
}

func TestDelegatedBacktestRunRejectsMissingStrategyID(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/strategies/404", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"message":"Strategy '404' not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		t.Fatal("backend should reject missing strategy before delegating run")
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"strategy_id": 404,
		"pairs":       []string{"BTC-USD", "ETH-USD"},
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if got["error"] != "STRATEGY_NOT_FOUND" {
		t.Fatalf("unexpected response body: %v", got)
	}
}

func TestDelegatedBacktestRun_OverwritesClientSnapshotWithBackendStrategy(t *testing.T) {
	requestBodyCh := make(chan map[string]interface{}, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode upstream request: %v", err)
		}
		requestBodyCh <- payload
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"strategy-snapshot-run","status":"queued"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_strategies (
			id, user_id, name, description, category, is_public, is_default, runtime_strategy, pair_selection_mode,
			runtime_network, runtime_subaccount, selected_markets, zscore_threshold, stats_window, max_half_life,
			usd_per_trade, usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs, manage_exits,
			place_trades, abort_all_positions, max_positions, max_drawdown_pct, stop_loss_pct, take_profit_pct,
			trailing_stop_pct, rebalance_interval_hours, position_timeout_hours, transaction_fee, slippage,
			starting_balance, candle_resolution, max_history_days, benchmark_symbol, risk_free_rate, initial_amount,
			usage_count, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		101, 1, "Desk Strategy", "authoritative snapshot", "pairs", false, false, "cointegration", "input",
		"testnet", 0, `["BTC-USD","ETH-USD","SOL-USD"]`, 1.35, 28, 18.0,
		22.0, 400.0, true, true, true,
		true, false, 6, 11.0, 1.8, 4.5,
		0.8, 12, 48, 0.0007, 0.002,
		2500.0, "4HOURS", 120, "ETH-USD", 0.05, 2500.0,
		0, now, now,
	); err != nil {
		t.Fatalf("insert strategy row: %v", err)
	}

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"strategy_id": 101,
		"pairs":       []string{"BTC-USD", "ETH-USD"},
		"strategy_payload_snapshot": map[string]interface{}{
			"id":               101,
			"name":             "stale client snapshot",
			"selected_markets": []string{"DOGE-USD", "XRP-USD"},
			"zscore_threshold": 9.9,
		},
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		var got map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&got)
		t.Fatalf("expected 200, got %d: %v", resp.StatusCode, got)
	}

	select {
	case payload := <-requestBodyCh:
		strategySnapshot, ok := payload["strategy_payload_snapshot"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected strategy_payload_snapshot map, got %T (%v)", payload["strategy_payload_snapshot"], payload["strategy_payload_snapshot"])
		}
		if strategySnapshot["name"] != "Desk Strategy" {
			t.Fatalf("expected authoritative name from backend DB, got %v", strategySnapshot["name"])
		}
		if strategySnapshot["benchmark_symbol"] != "ETH-USD" {
			t.Fatalf("expected authoritative benchmark_symbol, got %v", strategySnapshot["benchmark_symbol"])
		}
		if strategySnapshot["zscore_threshold"] != float64(1.35) {
			t.Fatalf("expected authoritative zscore_threshold=1.35, got %v", strategySnapshot["zscore_threshold"])
		}
		selectedMarkets, ok := strategySnapshot["selected_markets"].([]interface{})
		if !ok || len(selectedMarkets) != 3 || selectedMarkets[0] != "BTC-USD" {
			t.Fatalf("expected authoritative selected_markets from backend DB, got %T (%v)", strategySnapshot["selected_markets"], strategySnapshot["selected_markets"])
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream request payload")
	}
}

func TestDelegatedBotMarketData_ForwardsJWTCookieAliasAndPassthroughsStatus(t *testing.T) {
	upstreamAuthHeaderCh := make(chan string, 2)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/demo-bot/market-data", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":"upstream unauthorized"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/demo-bot/market-data", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.AddCookie(&http.Cookie{Name: "jwt", Value: token})

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("get delegated market data: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if got["error"] != "upstream unauthorized" {
		t.Fatalf("unexpected response body: %v", got)
	}
	if got["message"] != "upstream unauthorized" {
		t.Fatalf("expected passthrough message in response body: %v", got)
	}

	select {
	case authHeader := <-upstreamAuthHeaderCh:
		if authHeader != "Bearer "+token {
			t.Fatalf("unexpected upstream auth header: %q", authHeader)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream auth header")
	}
}

func TestDelegatedBacktestRun_NormalizesLegacyFlatPayload(t *testing.T) {
	requestBodyCh := make(chan map[string]interface{}, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode upstream request: %v", err)
		}
		requestBodyCh <- payload
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"normalized-run","status":"queued"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"start_date":          "2024-01-01",
		"end_date":            "2024-03-31",
		"name":                "legacy-run",
		"num_pairs":           12,
		"pair_selection_mode": "cointegration",
		"zscore_threshold":    1.75,
		"stats_window":        30,
		"usd_per_trade":       25,
		"benchmark_symbol":    "ETH-USD",
		"max_history_days":    120,
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	select {
	case payload := <-requestBodyCh:
		if _, exists := payload["num_pairs"]; exists {
			t.Fatalf("legacy field num_pairs should be removed: %v", payload)
		}
		if payload["max_pairs"] != float64(12) {
			t.Fatalf("expected max_pairs=12, got %v", payload["max_pairs"])
		}
		tp, ok := payload["trading_parameters"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected trading_parameters map, got %T (%v)", payload["trading_parameters"], payload["trading_parameters"])
		}
		if tp["zscore_threshold"] != float64(1.75) {
			t.Fatalf("expected zscore_threshold=1.75, got %v", tp["zscore_threshold"])
		}
		if tp["stats_window"] != float64(30) {
			t.Fatalf("expected stats_window=30, got %v", tp["stats_window"])
		}
		if tp["usd_per_trade"] != float64(25) {
			t.Fatalf("expected usd_per_trade=25, got %v", tp["usd_per_trade"])
		}
		if tp["pair_selection_mode"] != "cointegration" {
			t.Fatalf("expected pair_selection_mode propagated, got %v", tp["pair_selection_mode"])
		}
		if tp["benchmark_symbol"] != "ETH-USD" {
			t.Fatalf("expected benchmark_symbol propagated, got %v", tp["benchmark_symbol"])
		}
		if tp["max_history_days"] != float64(120) {
			t.Fatalf("expected max_history_days=120, got %v", tp["max_history_days"])
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream request payload")
	}
}

func TestDelegatedBacktestRun_DerivesSelectedPairLabelsAndContext(t *testing.T) {
	requestBodyCh := make(chan map[string]interface{}, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode upstream request: %v", err)
		}
		requestBodyCh <- payload
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"pair-label-run","status":"queued"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"pairs": []string{"BTC-USD", "ETH-USD", "SOL-USD"},
		"strategy_payload_snapshot": map[string]interface{}{
			"id":   4,
			"name": "UI Strategy Reference",
		},
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		var got map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&got)
		t.Fatalf("expected 200, got %d: %v", resp.StatusCode, got)
	}

	select {
	case payload := <-requestBodyCh:
		pairs, ok := payload["pairs"].([]interface{})
		if !ok || len(pairs) != 3 {
			t.Fatalf("expected upstream pairs market list, got %T (%v)", payload["pairs"], payload["pairs"])
		}
		selectedPairs, ok := payload["selected_pairs"].([]interface{})
		if !ok {
			t.Fatalf("expected selected_pairs array, got %T (%v)", payload["selected_pairs"], payload["selected_pairs"])
		}
		expected := []string{"BTC-USD/ETH-USD", "BTC-USD/SOL-USD", "ETH-USD/SOL-USD"}
		if len(selectedPairs) != len(expected) {
			t.Fatalf("expected %d selected_pairs, got %d (%v)", len(expected), len(selectedPairs), selectedPairs)
		}
		for i, want := range expected {
			if selectedPairs[i] != want {
				t.Fatalf("expected selected_pairs[%d]=%q, got %v", i, want, selectedPairs[i])
			}
		}
		if payload["source"] != "ui" {
			t.Fatalf("expected source=ui, got %v", payload["source"])
		}
		if payload["requested_by_user_id"] != float64(1) {
			t.Fatalf("expected requested_by_user_id=1, got %v", payload["requested_by_user_id"])
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream request payload")
	}
}

func TestDelegatedBacktestRun_PreservesExactUIPayloadContract(t *testing.T) {
	requestBodyCh := make(chan map[string]interface{}, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, r *http.Request) {
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode upstream request: %v", err)
		}
		requestBodyCh <- payload
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"ui-contract-run","status":"queued"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO backtest_strategies (
			id, user_id, name, description, category, is_public, is_default, runtime_strategy, pair_selection_mode,
			runtime_network, runtime_subaccount, selected_markets, zscore_threshold, stats_window, max_half_life,
			usd_per_trade, usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs, manage_exits,
			place_trades, abort_all_positions, max_positions, max_drawdown_pct, stop_loss_pct, take_profit_pct,
			trailing_stop_pct, rebalance_interval_hours, position_timeout_hours, transaction_fee, slippage,
			starting_balance, candle_resolution, max_history_days, benchmark_symbol, risk_free_rate, initial_amount,
			usage_count, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		4, 1, "Aggressive Strategy", "Aggressive strategy with lower thresholds for frequent trading", "pairs", false, false, "cointegration", "liquidity",
		"testnet", 0, `["BTC-USD","ETH-USD","LINK-USD","AVAX-USD"]`, 1.0, 14, 8.0,
		10.0, 300.0, true, true, true,
		true, false, 5, 15.0, 2.0, 5.0,
		1.0, 24, 72, 0.0005, 0.001,
		300.0, "1HOUR", 90, "BTC-USD", 0.02, 300.0,
		0, now, now,
	); err != nil {
		t.Fatalf("insert strategy row: %v", err)
	}

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{
		"start_date":          "2026-04-03",
		"end_date":            "2026-05-03",
		"name":                "terert Backtest",
		"description":         "Aggressive strategy with lower thresholds for frequent trading",
		"strategy_id":         4,
		"environment":         "testnet",
		"initial_balance":     300,
		"pair_selection_mode": "liquidity",
		"max_pairs":           4,
		"pairs":               []string{"BTC-USD", "ETH-USD", "LINK-USD", "AVAX-USD"},
		"trading_parameters": map[string]interface{}{
			"zscore_threshold":         1,
			"stats_window":             14,
			"max_half_life":            8,
			"usd_per_trade":            10,
			"usd_min_collateral":       300,
			"close_at_zscore_cross":    true,
			"find_cointegrated_pairs":  true,
			"manage_exits":             true,
			"place_trades":             true,
			"abort_all_positions":      false,
			"max_positions":            5,
			"max_drawdown_pct":         15,
			"stop_loss_pct":            2,
			"take_profit_pct":          5,
			"trailing_stop_pct":        1,
			"rebalance_interval_hours": 24,
			"position_timeout_hours":   72,
			"transaction_fee":          0.0005,
			"slippage":                 0.001,
			"risk_free_rate":           0.02,
			"benchmark_symbol":         "BTC-USD",
			"max_history_days":         90,
			"resolution":               "1HOUR",
			"candle_resolution":        "1HOUR",
			"pair_selection_mode":      "liquidity",
		},
		"source": "ui",
		"selected_pairs": []string{
			"BTC-USD/ETH-USD",
			"BTC-USD/LINK-USD",
			"BTC-USD/AVAX-USD",
			"ETH-USD/LINK-USD",
			"ETH-USD/AVAX-USD",
			"LINK-USD/AVAX-USD",
		},
	})
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		var got map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&got)
		t.Fatalf("expected 200, got %d: %v", resp.StatusCode, got)
	}

	select {
	case payload := <-requestBodyCh:
		if payload["strategy_id"] != float64(4) {
			t.Fatalf("expected strategy_id=4, got %v", payload["strategy_id"])
		}
		if payload["source"] != "ui" {
			t.Fatalf("expected source=ui, got %v", payload["source"])
		}
		if payload["environment"] != "testnet" {
			t.Fatalf("expected environment=testnet, got %v", payload["environment"])
		}
		if payload["requested_by_user_id"] != float64(1) {
			t.Fatalf("expected requested_by_user_id=1, got %v", payload["requested_by_user_id"])
		}
		if payload["max_pairs"] != float64(4) {
			t.Fatalf("expected max_pairs=4, got %v", payload["max_pairs"])
		}

		pairs, ok := payload["pairs"].([]interface{})
		if !ok || len(pairs) != 4 {
			t.Fatalf("expected pairs market list of 4, got %T (%v)", payload["pairs"], payload["pairs"])
		}
		if pairs[0] != "BTC-USD" || pairs[1] != "ETH-USD" || pairs[2] != "LINK-USD" || pairs[3] != "AVAX-USD" {
			t.Fatalf("unexpected pairs ordering/content: %v", pairs)
		}

		selectedPairs, ok := payload["selected_pairs"].([]interface{})
		if !ok || len(selectedPairs) != 6 {
			t.Fatalf("expected selected_pairs list of 6, got %T (%v)", payload["selected_pairs"], payload["selected_pairs"])
		}
		expectedSelected := []string{
			"BTC-USD/ETH-USD",
			"BTC-USD/LINK-USD",
			"BTC-USD/AVAX-USD",
			"ETH-USD/LINK-USD",
			"ETH-USD/AVAX-USD",
			"LINK-USD/AVAX-USD",
		}
		for i, want := range expectedSelected {
			if selectedPairs[i] != want {
				t.Fatalf("expected selected_pairs[%d]=%q, got %v", i, want, selectedPairs[i])
			}
		}

		tradingParameters, ok := payload["trading_parameters"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected trading_parameters map, got %T (%v)", payload["trading_parameters"], payload["trading_parameters"])
		}
		if tradingParameters["pair_selection_mode"] != "liquidity" {
			t.Fatalf("expected pair_selection_mode=liquidity, got %v", tradingParameters["pair_selection_mode"])
		}
		if tradingParameters["resolution"] != "1HOUR" {
			t.Fatalf("expected resolution=1HOUR, got %v", tradingParameters["resolution"])
		}
		if tradingParameters["candle_resolution"] != "1HOUR" {
			t.Fatalf("expected candle_resolution=1HOUR, got %v", tradingParameters["candle_resolution"])
		}

		strategySnapshot, ok := payload["strategy_payload_snapshot"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected strategy_payload_snapshot map, got %T (%v)", payload["strategy_payload_snapshot"], payload["strategy_payload_snapshot"])
		}
		if strategySnapshot["id"] != float64(4) {
			t.Fatalf("expected strategy_payload_snapshot.id=4, got %v", strategySnapshot["id"])
		}
		if strategySnapshot["name"] != "Aggressive Strategy" {
			t.Fatalf("expected strategy_payload_snapshot.name from backend strategy, got %v", strategySnapshot["name"])
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream request payload")
	}
}

func TestDelegatedBacktestRun_SyncsRunIntoLocalDB(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"db-sync-run","status":"queued","start_date":"2025-01-01","end_date":"2025-01-31","max_pairs":7,"total_markets":20}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post delegated run: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var status string
	var userID int
	var numPairs int
	var totalMarkets int
	err = dbConn.QueryRow(`SELECT status, user_id, num_pairs, total_markets FROM backtest_runs WHERE run_id = ?`, "db-sync-run").
		Scan(&status, &userID, &numPairs, &totalMarkets)
	if err != nil {
		t.Fatalf("query synced row: %v", err)
	}

	if status != "queued" {
		t.Fatalf("expected queued status, got %q", status)
	}
	if userID <= 0 {
		t.Fatalf("expected user_id > 0, got %d", userID)
	}
	if numPairs != 7 {
		t.Fatalf("expected num_pairs=7, got %d", numPairs)
	}
	if totalMarkets != 20 {
		t.Fatalf("expected total_markets=20, got %d", totalMarkets)
	}
}

func TestDelegatedBacktestStatus_UpdatesLocalDBStatus(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"db-sync-status","status":"queued","start_date":"2025-02-01","end_date":"2025-02-28","num_pairs":5,"total_markets":12}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/db-sync-status/status", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"db-sync-status","status":"completed","total_trades":42,"total_pnl_usd":123.5}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	createReq, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new create request: %v", err)
	}
	createReq.Header.Set("Content-Type", "application/json")
	createReq.Header.Set("Authorization", "Bearer "+token)
	createResp, err := http.DefaultClient.Do(createReq)
	if err != nil {
		t.Fatalf("create delegated run: %v", err)
	}
	_ = createResp.Body.Close()

	statusReq, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/db-sync-status/status", nil)
	if err != nil {
		t.Fatalf("new status request: %v", err)
	}
	statusReq.Header.Set("Authorization", "Bearer "+token)
	statusResp, err := http.DefaultClient.Do(statusReq)
	if err != nil {
		t.Fatalf("get delegated status: %v", err)
	}
	defer func() { _ = statusResp.Body.Close() }()

	if statusResp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", statusResp.StatusCode)
	}

	var status string
	var totalTrades sql.NullInt64
	var totalPnLUSD sql.NullFloat64
	err = dbConn.QueryRow(`SELECT status, total_trades, total_pnl_usd FROM backtest_runs WHERE run_id = ?`, "db-sync-status").
		Scan(&status, &totalTrades, &totalPnLUSD)
	if err != nil {
		t.Fatalf("query synced status row: %v", err)
	}

	if status != "completed" {
		t.Fatalf("expected completed status, got %q", status)
	}
	if !totalTrades.Valid || totalTrades.Int64 != 42 {
		t.Fatalf("expected total_trades=42, got %+v", totalTrades)
	}
	if !totalPnLUSD.Valid || totalPnLUSD.Float64 != 123.5 {
		t.Fatalf("expected total_pnl_usd=123.5, got %+v", totalPnLUSD)
	}
}

func TestDelegatedBacktestTrades_SyncsChildRowsIntoLocalDB(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"child-sync-run","status":"queued","start_date":"2025-03-01","end_date":"2025-03-31","num_pairs":5,"total_markets":10}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/child-sync-run/trades", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"trades":[{"trade_id":"t-1","market_1":"BTC-USD","market_2":"ETH-USD","entry_timestamp":"2025-03-05T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.2,"side_1":"BUY","side_2":"SELL","size_1":1,"size_2":2,"pnl":12.5,"pnl_pct":0.8,"hedge_ratio":0.5}]}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	createReq, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	createReq.Header.Set("Authorization", "Bearer "+token)
	createReq.Header.Set("Content-Type", "application/json")
	createResp, err := http.DefaultClient.Do(createReq)
	if err != nil {
		t.Fatalf("create run request failed: %v", err)
	}
	_ = createResp.Body.Close()

	tradesReq, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/child-sync-run/trades", nil)
	tradesReq.Header.Set("Authorization", "Bearer "+token)
	tradesResp, err := http.DefaultClient.Do(tradesReq)
	if err != nil {
		t.Fatalf("trades request failed: %v", err)
	}
	_ = tradesResp.Body.Close()

	var count int
	err = dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_trades WHERE trade_id = ?`, "t-1").Scan(&count)
	if err != nil {
		t.Fatalf("query trades sync row: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected synced trade row count 1, got %d", count)
	}

	// Dedupe check: second sync updates existing row instead of inserting duplicate.
	tradesResp2, err := http.DefaultClient.Do(tradesReq)
	if err != nil {
		t.Fatalf("second trades request failed: %v", err)
	}
	_ = tradesResp2.Body.Close()
	err = dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_trades WHERE trade_id = ?`, "t-1").Scan(&count)
	if err != nil {
		t.Fatalf("query trades dedupe row: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected deduped trade row count 1, got %d", count)
	}
}

func TestDelegatedBacktestPositionSnapshots_SyncsChildRowsIntoLocalDB(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"child-sync-pos","status":"queued","start_date":"2025-04-01","end_date":"2025-04-30","num_pairs":3,"total_markets":8}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/child-sync-pos/position-snapshots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"position_snapshots":[{"position_id":"p-1","market_1":"BTC-USD","market_2":"ETH-USD","status":"OPEN","entry_timestamp":"2025-04-03T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.1,"size_1":1,"size_2":2,"side_1":"BUY","side_2":"SELL","hedge_ratio":0.6}]}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	createReq, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	createReq.Header.Set("Authorization", "Bearer "+token)
	createReq.Header.Set("Content-Type", "application/json")
	createResp, err := http.DefaultClient.Do(createReq)
	if err != nil {
		t.Fatalf("create run request failed: %v", err)
	}
	_ = createResp.Body.Close()

	posReq, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/child-sync-pos/position-snapshots", nil)
	posReq.Header.Set("Authorization", "Bearer "+token)
	posResp, err := http.DefaultClient.Do(posReq)
	if err != nil {
		t.Fatalf("position snapshots request failed: %v", err)
	}
	_ = posResp.Body.Close()

	var count int
	err = dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_positions WHERE position_id = ?`, "p-1").Scan(&count)
	if err != nil {
		t.Fatalf("query position sync row: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected synced position row count 1, got %d", count)
	}
}

func TestDelegatedBacktestSyncHealth_ReturnsCountsByRun(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"health-run","status":"queued","start_date":"2025-05-01","end_date":"2025-05-31","num_pairs":2,"total_markets":6}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/health-run/trades", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"trades":[{"trade_id":"h-trade","market_1":"BTC-USD","market_2":"ETH-USD","entry_timestamp":"2025-05-05T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.3,"side_1":"BUY","side_2":"SELL","size_1":1,"size_2":2,"hedge_ratio":0.5}]}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/health-run/position-snapshots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"position_snapshots":[{"position_id":"h-pos","market_1":"BTC-USD","market_2":"ETH-USD","status":"OPEN","entry_timestamp":"2025-05-05T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.2,"size_1":1,"size_2":2,"side_1":"BUY","side_2":"SELL","hedge_ratio":0.6}]}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body := validDelegatedBacktestRunBody(t)
	createReq, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/run", bytes.NewReader(body))
	createReq.Header.Set("Authorization", "Bearer "+token)
	createReq.Header.Set("Content-Type", "application/json")
	createResp, err := http.DefaultClient.Do(createReq)
	if err != nil {
		t.Fatalf("create run request failed: %v", err)
	}
	_ = createResp.Body.Close()

	var runPK int
	if err := dbConn.QueryRow(`SELECT id FROM backtest_runs WHERE run_id = ?`, "health-run").Scan(&runPK); err != nil {
		t.Fatalf("resolve run pk: %v", err)
	}

	if _, err := dbConn.Exec(`
		INSERT INTO backtest_trades (
			run_id_fk, trade_id, market_1, market_2, entry_timestamp,
			entry_price_1, entry_price_2, entry_z_score,
			side_1, side_2, size_1, size_2,
			hedge_ratio, transaction_fee, slippage
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, runPK, "h-trade", "BTC-USD", "ETH-USD", time.Now().UTC(), 100.0, 200.0, 1.3, "BUY", "SELL", 1.0, 2.0, 0.5, 0.0, 0.0); err != nil {
		t.Fatalf("seed backtest_trades row: %v", err)
	}

	if _, err := dbConn.Exec(`
		INSERT INTO backtest_positions (
			run_id_fk, position_id, market_1, market_2, status,
			entry_timestamp, entry_price_1, entry_price_2, entry_z_score,
			size_1, size_2, side_1, side_2, hedge_ratio
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, runPK, "h-pos", "BTC-USD", "ETH-USD", "OPEN", time.Now().UTC(), 100.0, 200.0, 1.2, 1.0, 2.0, "BUY", "SELL", 0.6); err != nil {
		t.Fatalf("seed backtest_positions row: %v", err)
	}

	healthReq, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/sync-health?run_id=health-run", nil)
	healthReq.Header.Set("Authorization", "Bearer "+token)
	healthResp, err := http.DefaultClient.Do(healthReq)
	if err != nil {
		t.Fatalf("sync-health request failed: %v", err)
	}
	defer func() { _ = healthResp.Body.Close() }()

	if healthResp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", healthResp.StatusCode)
	}

	var payload struct {
		Success bool `json:"success"`
		Data    struct {
			Runs []struct {
				RunID         string `json:"run_id"`
				Trades        int    `json:"trades"`
				Positions     int    `json:"positions"`
				Candles       int    `json:"candles"`
				RunAgeSec     int64  `json:"run_age_seconds"`
				SyncLagSec    int64  `json:"sync_lag_seconds"`
				QualityIssues int    `json:"quality_issues"`
			} `json:"runs"`
			Count int `json:"count"`
		} `json:"data"`
	}
	if err := json.NewDecoder(healthResp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode sync-health response: %v", err)
	}

	if !payload.Success {
		t.Fatal("expected success=true")
	}
	if payload.Data.Count < 1 || len(payload.Data.Runs) < 1 {
		t.Fatalf("expected at least one run in sync-health response: %+v", payload.Data)
	}
	if payload.Data.Runs[0].RunID != "health-run" {
		t.Fatalf("unexpected run id in sync-health: %s", payload.Data.Runs[0].RunID)
	}
	if payload.Data.Runs[0].Trades < 1 {
		t.Fatalf("expected trades count >= 1, got %d", payload.Data.Runs[0].Trades)
	}
	if payload.Data.Runs[0].Positions < 1 {
		t.Fatalf("expected positions count >= 1, got %d", payload.Data.Runs[0].Positions)
	}
	if payload.Data.Runs[0].Candles != 0 {
		t.Fatalf("expected candles count 0 in seeded test, got %d", payload.Data.Runs[0].Candles)
	}
	if payload.Data.Runs[0].RunAgeSec < 0 {
		t.Fatalf("expected run_age_seconds >= 0, got %d", payload.Data.Runs[0].RunAgeSec)
	}
	if payload.Data.Runs[0].SyncLagSec < 0 {
		t.Fatalf("expected sync_lag_seconds >= 0, got %d", payload.Data.Runs[0].SyncLagSec)
	}
	if payload.Data.Runs[0].QualityIssues < 0 {
		t.Fatalf("expected quality_issues >= 0, got %d", payload.Data.Runs[0].QualityIssues)
	}
}

func TestDelegatedBacktestResync_RefreshesRunAndChildren(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/resync-run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"resync-run","status":"completed","start_date":"2025-06-01","end_date":"2025-06-30","num_pairs":4,"total_markets":9}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/resync-run/trades", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"trades":[{"trade_id":"resync-trade","market_1":"BTC-USD","market_2":"ETH-USD","entry_timestamp":"2025-06-10T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.1,"side_1":"BUY","side_2":"SELL","size_1":1,"size_2":2,"hedge_ratio":0.5}]}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/resync-run/position-snapshots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"position_snapshots":[{"position_id":"resync-pos","market_1":"BTC-USD","market_2":"ETH-USD","status":"OPEN","entry_timestamp":"2025-06-10T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.1,"size_1":1,"size_2":2,"side_1":"BUY","side_2":"SELL","hedge_ratio":0.5}]}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/resync-run/performance-metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"candles":[{"market":"BTC-USD","timestamp":"2025-06-10T00:00:00Z","resolution":"1HOUR","open":100,"high":101,"low":99,"close":100.5,"volume":12}]}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	resyncReq, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/resync-run/resync", nil)
	resyncReq.Header.Set("Authorization", "Bearer "+token)
	resyncResp, err := http.DefaultClient.Do(resyncReq)
	if err != nil {
		t.Fatalf("resync request failed: %v", err)
	}
	defer func() { _ = resyncResp.Body.Close() }()

	if resyncResp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resyncResp.StatusCode)
	}

	var resyncPayload map[string]interface{}
	if err := json.NewDecoder(resyncResp.Body).Decode(&resyncPayload); err != nil {
		t.Fatalf("decode resync payload: %v", err)
	}
	data, ok := resyncPayload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected resync data object, got %T (%v)", resyncPayload["data"], resyncPayload["data"])
	}
	if data["run_id"] != "resync-run" {
		t.Fatalf("expected run_id=resync-run in resync response, got %v", data["run_id"])
	}
	if data["status"] != "completed" {
		t.Fatalf("expected status=completed in resync response, got %v", data["status"])
	}
	if data["progress_percent"] != float64(0) || data["progress_pct"] != float64(0) || data["progress"] != float64(0) {
		t.Fatalf("expected progress aliases to default to 0 in resync response, got %+v", data)
	}
	if data["sync_state"] != "completed" {
		t.Fatalf("expected sync_state=completed, got %v", data["sync_state"])
	}
	if _, ok := data["current_task"]; !ok {
		t.Fatalf("expected current_task key in resync response data")
	}
	if _, ok := data["current_pair"]; !ok {
		t.Fatalf("expected current_pair key in resync response data")
	}

	var runCount int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_runs WHERE run_id = ?`, "resync-run").Scan(&runCount); err != nil {
		t.Fatalf("query run count: %v", err)
	}
	if runCount != 1 {
		t.Fatalf("expected run count 1, got %d", runCount)
	}

	var tradeCount int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_trades WHERE trade_id = ?`, "resync-trade").Scan(&tradeCount); err != nil {
		t.Fatalf("query trade count: %v", err)
	}
	if tradeCount != 1 {
		t.Fatalf("expected trade count 1, got %d", tradeCount)
	}

	var posCount int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_positions WHERE position_id = ?`, "resync-pos").Scan(&posCount); err != nil {
		t.Fatalf("query position count: %v", err)
	}
	if posCount != 1 {
		t.Fatalf("expected position count 1, got %d", posCount)
	}

	var candleCount int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM backtest_candles WHERE market = ?`, "BTC-USD").Scan(&candleCount); err != nil {
		t.Fatalf("query candle count: %v", err)
	}
	if candleCount != 1 {
		t.Fatalf("expected candle count 1, got %d", candleCount)
	}
}

func TestDelegatedBacktestContract_EmptyStatesReturn200WithArrays(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/empty-run/logs", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/empty-run/analytics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/empty-run/position-snapshots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/empty-run/trades/detailed", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)

	type endpointCase struct {
		path         string
		arrayPathKey string
	}
	checks := []endpointCase{
		{path: "/api/v1/backtests/empty-run/logs", arrayPathKey: "logs"},
		{path: "/api/v1/backtests/empty-run/analytics", arrayPathKey: "daily_pnl"},
		{path: "/api/v1/backtests/empty-run/position-snapshots", arrayPathKey: "snapshots"},
		{path: "/api/v1/backtests/empty-run/positions/snapshots", arrayPathKey: "snapshots"},
		{path: "/api/v1/backtests/empty-run/trades/detailed", arrayPathKey: "trades"},
	}

	for _, check := range checks {
		req, _ := http.NewRequest(http.MethodGet, backendServer.URL+check.path, nil)
		req.Header.Set("Authorization", "Bearer "+token)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("request %s failed: %v", check.path, err)
		}
		if resp.StatusCode != http.StatusOK {
			_ = resp.Body.Close()
			t.Fatalf("expected 200 for %s, got %d", check.path, resp.StatusCode)
		}
		var payload map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
			_ = resp.Body.Close()
			t.Fatalf("decode %s response: %v", check.path, err)
		}
		_ = resp.Body.Close()
		data, ok := payload["data"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected data object for %s", check.path)
		}
		if _, ok := data[check.arrayPathKey].([]interface{}); !ok {
			t.Fatalf("expected data.%s array for %s", check.arrayPathKey, check.path)
		}
	}
}

func TestDelegatedBacktestAnalyticsSummary_DelegatesUpstreamPayload(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/summary-run/analytics/summary", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":{"run_id":"summary-run","total_pnl_usd":123.45,"total_trades":7,"win_rate":57.1},"message":"ok"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/summary-run/analytics/summary", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("summary request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode summary payload: %v", err)
	}
	data, ok := payload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected data object in summary payload, got %T (%v)", payload["data"], payload["data"])
	}
	if data["run_id"] != "summary-run" {
		t.Fatalf("expected run_id=summary-run, got %v", data["run_id"])
	}
	if data["total_pnl_usd"] != float64(123.45) {
		t.Fatalf("expected total_pnl_usd=123.45, got %v", data["total_pnl_usd"])
	}
	if data["total_pnl"] != float64(123.45) {
		t.Fatalf("expected total_pnl alias=123.45, got %v", data["total_pnl"])
	}
	if data["total_trades"] != float64(7) {
		t.Fatalf("expected total_trades=7, got %v", data["total_trades"])
	}
	if data["win_rate"] != float64(57.1) {
		t.Fatalf("expected win_rate=57.1, got %v", data["win_rate"])
	}
}

func TestDelegatedBacktestStatus_DefaultProgressFields(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/pending-run/status", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"pending-run","status":"pending"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/pending-run/status", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("status request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode status payload: %v", err)
	}
	data, ok := payload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected data object in status payload, got %T (%v)", payload["data"], payload["data"])
	}
	if payload["progress_pct"] != float64(0) {
		t.Fatalf("expected progress_pct=0, got %v", payload["progress_pct"])
	}
	if data["progress_pct"] != float64(0) || data["progress_percent"] != float64(0) || data["progress"] != float64(0) {
		t.Fatalf("expected zero progress aliases in status data, got %+v", data)
	}
	if _, ok := payload["current_task"]; !ok {
		t.Fatalf("expected current_task key in status payload")
	}
	if _, ok := payload["current_pair"]; !ok {
		t.Fatalf("expected current_pair key in status payload")
	}
	if _, ok := data["current_task"]; !ok {
		t.Fatalf("expected current_task key in status data")
	}
	if _, ok := data["current_pair"]; !ok {
		t.Fatalf("expected current_pair key in status data")
	}
}

func TestDelegatedBacktestStatus_PreservesRunningProgressAndTaskFields(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/running-run/status", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":{"run_id":"running-run","status":"running","progress_percent":61,"current_task":"scanning pairs","current_pair":"BTC-USD/ETH-USD"},"message":"ok"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/running-run/status", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("running status request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode running status payload: %v", err)
	}
	data, ok := payload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected data object in running status payload, got %T (%v)", payload["data"], payload["data"])
	}
	if payload["progress_pct"] != float64(61) || payload["progress_percent"] != float64(61) || payload["progress"] != float64(61) {
		t.Fatalf("expected root progress aliases=61, got %+v", payload)
	}
	if data["progress_pct"] != float64(61) || data["progress_percent"] != float64(61) || data["progress"] != float64(61) {
		t.Fatalf("expected data progress aliases=61, got %+v", data)
	}
	if payload["current_task"] != "scanning pairs" || payload["current_pair"] != "BTC-USD/ETH-USD" {
		t.Fatalf("expected root running task fields, got %+v", payload)
	}
	if data["current_task"] != "scanning pairs" || data["current_pair"] != "BTC-USD/ETH-USD" {
		t.Fatalf("expected data running task fields, got %+v", data)
	}
}

func TestDelegatedBacktestDetails_NormalizesNestedEnvelopeAndSyncsRun(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/details-run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"run_id":"details-run","status":"running","start_date":"2025-08-01","end_date":"2025-08-31","num_pairs":4,"total_markets":11,"progress_percent":37,"total_pnl":88.4,"max_drawdown":4.6},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/details-run", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("details request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode details payload: %v", err)
	}
	data, ok := payload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected nested data payload, got %T (%v)", payload["data"], payload["data"])
	}
	if data["progress_percent"] != float64(37) || data["progress_pct"] != float64(37) || data["progress"] != float64(37) {
		t.Fatalf("expected normalized progress aliases = 37, got %+v", data)
	}
	if value, exists := data["win_rate"]; !exists || value != nil {
		t.Fatalf("expected explicit null win_rate, got exists=%v value=%v", exists, value)
	}
	if data["max_drawdown_pct"] != float64(4.6) {
		t.Fatalf("expected max_drawdown_pct=4.6, got %v", data["max_drawdown_pct"])
	}

	var status string
	var totalPnL sql.NullFloat64
	err = dbConn.QueryRow(`SELECT status, total_pnl FROM backtest_runs WHERE run_id = ?`, "details-run").Scan(&status, &totalPnL)
	if err != nil {
		t.Fatalf("query synced details row: %v", err)
	}
	if status != "running" {
		t.Fatalf("expected synced status running, got %q", status)
	}
	if !totalPnL.Valid || totalPnL.Float64 != 88.4 {
		t.Fatalf("expected synced total_pnl=88.4, got %+v", totalPnL)
	}
}

func TestDelegatedBacktestDetails_PreservesZeroMetricsInSync(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/zero-metrics-run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"zero-metrics-run","status":"completed","start_date":"2025-09-01","end_date":"2025-09-30","num_pairs":1,"total_markets":2,"total_trades":0,"winning_trades":0,"losing_trades":0,"win_rate":0,"total_pnl":0,"total_pnl_usd":0}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/zero-metrics-run", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("zero metrics details request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var totalTrades sql.NullInt64
	var winRate sql.NullFloat64
	var totalPnL sql.NullFloat64
	var totalPnLUSD sql.NullFloat64
	err = dbConn.QueryRow(`SELECT total_trades, win_rate, total_pnl, total_pnl_usd FROM backtest_runs WHERE run_id = ?`, "zero-metrics-run").
		Scan(&totalTrades, &winRate, &totalPnL, &totalPnLUSD)
	if err != nil {
		t.Fatalf("query synced zero metrics row: %v", err)
	}
	if !totalTrades.Valid || totalTrades.Int64 != 0 {
		t.Fatalf("expected total_trades valid zero, got %+v", totalTrades)
	}
	if !winRate.Valid || winRate.Float64 != 0 {
		t.Fatalf("expected win_rate valid zero, got %+v", winRate)
	}
	if !totalPnL.Valid || totalPnL.Float64 != 0 {
		t.Fatalf("expected total_pnl valid zero, got %+v", totalPnL)
	}
	if !totalPnLUSD.Valid || totalPnLUSD.Float64 != 0 {
		t.Fatalf("expected total_pnl_usd valid zero, got %+v", totalPnLUSD)
	}
}
