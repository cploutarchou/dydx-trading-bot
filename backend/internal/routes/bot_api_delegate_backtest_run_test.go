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

	dbConn, err := sql.Open("sqlite", ":memory:")
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
