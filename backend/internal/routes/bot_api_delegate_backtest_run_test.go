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
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupDelegatedBacktestAuthRouter(t *testing.T, upstream http.Handler) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	const secret = "delegated-backtest-run-test-secret"
	t.Setenv("JWT_SECRET_KEY", secret)
	t.Setenv("APP_ENV", "test")

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
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		last_login DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create users table: %v", err)
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
		error_message TEXT,
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

	config.LoadConfig()
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

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstream)
	upstreamServer := httptest.NewServer(upstream)
	t.Cleanup(upstreamServer.Close)

	apiClient := services.NewBotAPIClient(upstreamServer.URL, "")
	backtestSyncRepo := repository.NewBacktestSyncRepository(dbConn)
	backtestSyncService := services.NewBacktestSyncService(backtestSyncRepo)

	router = gin.New()
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

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestUser(t, backendServer.URL)
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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

func TestDelegatedBotMarketData_ForwardsJWTCookieAliasAndPassthroughsStatus(t *testing.T) {
	upstreamAuthHeaderCh := make(chan string, 1)
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
	body, _ := json.Marshal(map[string]interface{}{"strategy": "pairs"})
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
				RunID     string `json:"run_id"`
				Trades    int    `json:"trades"`
				Positions int    `json:"positions"`
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
	if payload["progress_pct"] != float64(0) {
		t.Fatalf("expected progress_pct=0, got %v", payload["progress_pct"])
	}
	if _, ok := payload["current_task"]; !ok {
		t.Fatalf("expected current_task key in status payload")
	}
	if _, ok := payload["current_pair"]; !ok {
		t.Fatalf("expected current_pair key in status payload")
	}
}
