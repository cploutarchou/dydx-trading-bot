//go:build integration

package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupStrategyRuntimeRouterWithExecutionStateSchema(t *testing.T, upstream http.Handler, legacyExecutionStateSchema bool) (*gin.Engine, *sql.DB, *httptest.Server) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	upstreamServer := httptest.NewServer(upstream)
	t.Setenv("BOT_API_URL", upstreamServer.URL)
	t.Setenv("APP_ENV", "test")
	t.Setenv("ENCRYPTION_KEY", "strategy-runtime-test-key-123456")

	const secret = "strategy-runtime-contract-secret"
	t.Setenv("JWT_SECRET_KEY", secret)
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             secret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", "file:strategy-runtime-test?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	schema := []string{
		`CREATE TABLE users (
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
		);`,
		`CREATE TABLE backtest_strategies (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			name TEXT NOT NULL,
			description TEXT,
			category TEXT,
			is_public BOOLEAN NOT NULL DEFAULT 0,
			is_default BOOLEAN NOT NULL DEFAULT 0,
			runtime_strategy TEXT NOT NULL DEFAULT 'cointegration',
			zscore_threshold REAL NOT NULL,
			stats_window INTEGER NOT NULL,
			max_half_life REAL NOT NULL,
			usd_per_trade REAL NOT NULL,
			usd_min_collateral REAL NOT NULL,
			close_at_zscore_cross BOOLEAN NOT NULL,
			find_cointegrated_pairs BOOLEAN NOT NULL,
			manage_exits BOOLEAN NOT NULL,
			place_trades BOOLEAN NOT NULL,
			abort_all_positions BOOLEAN NOT NULL,
			max_positions INTEGER NOT NULL,
			max_drawdown_pct REAL NOT NULL,
			stop_loss_pct REAL NOT NULL,
			take_profit_pct REAL NOT NULL,
			trailing_stop_pct REAL NOT NULL,
			rebalance_interval_hours INTEGER NOT NULL,
			position_timeout_hours INTEGER NOT NULL,
			transaction_fee REAL NOT NULL,
			slippage REAL NOT NULL,
			starting_balance REAL NOT NULL,
			candle_resolution TEXT NOT NULL,
			max_history_days INTEGER NOT NULL,
			benchmark_symbol TEXT NOT NULL,
			risk_free_rate REAL NOT NULL,
			initial_amount REAL NOT NULL,
			usage_count INTEGER NOT NULL DEFAULT 0,
			last_used_at DATETIME,
			deleted_at DATETIME,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL
		);`,
		`CREATE TABLE strategy_execution_states (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			strategy_id INTEGER NOT NULL UNIQUE,
			%s
		);`,
		`CREATE TABLE dydx_keys (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			network TEXT NOT NULL,
			chain_address TEXT NOT NULL,
			encrypted_secret TEXT NOT NULL,
			secret_hash TEXT NOT NULL DEFAULT '',
			secret_masked TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT 1,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL
		);`,
		`CREATE TABLE bot_instances (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			instance_id TEXT NOT NULL UNIQUE,
			instance_name TEXT,
			user_id INTEGER,
			status TEXT,
			network TEXT,
			strategy TEXT,
			config TEXT,
			trading_params TEXT,
			total_trades INTEGER DEFAULT 0,
			total_pnl REAL,
			current_balance REAL,
			starting_balance REAL,
			process_id INTEGER,
			pid TEXT,
			host TEXT,
			port INTEGER,
			error_message TEXT,
			last_error_at DATETIME,
			started_at DATETIME,
			stopped_at DATETIME,
			created_at DATETIME,
			updated_at DATETIME
		);`,
	}
	if legacyExecutionStateSchema {
		schema[2] = fmt.Sprintf(schema[2],
			`enabled BOOLEAN DEFAULT NULL,
			status TEXT DEFAULT NULL,
			trades_executed INTEGER DEFAULT NULL,
			pnl REAL DEFAULT NULL,
			pnl_pct REAL DEFAULT NULL,
			last_error TEXT DEFAULT NULL,
			error_count INTEGER DEFAULT NULL,
			last_error_at DATETIME DEFAULT NULL,
			config_snapshot JSON DEFAULT NULL,
			last_started DATETIME DEFAULT NULL,
			last_stopped DATETIME DEFAULT NULL,
			last_trade_at DATETIME DEFAULT NULL,
			uptime_seconds INTEGER DEFAULT NULL,
			last_cointegration_check DATETIME DEFAULT NULL,
			active_pairs_count INTEGER DEFAULT NULL,
			open_positions_count INTEGER DEFAULT NULL,
			max_drawdown REAL DEFAULT NULL,
			sharpe_ratio REAL DEFAULT NULL,
			win_rate REAL DEFAULT NULL,
			created_at DATETIME DEFAULT NULL,
			updated_at DATETIME DEFAULT NULL`)
	} else {
		schema[2] = fmt.Sprintf(schema[2],
			`is_running BOOLEAN NOT NULL DEFAULT 0,
			last_run_at DATETIME,
			next_run_at DATETIME,
			state TEXT,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL`)
	}
	for _, statement := range schema {
		if _, err := dbConn.Exec(statement); err != nil {
			t.Fatalf("create schema: %v", err)
		}
	}

	hash, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate password hash: %v", err)
	}
	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"runtime-user",
		"runtime-user@example.local",
		"Runtime User",
		"",
		string(hash),
		true,
		false,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert user: %v", err)
	}

	if _, err := dbConn.Exec(
		`INSERT INTO backtest_strategies (
			id, user_id, name, description, category, is_public, is_default,
			runtime_strategy,
			zscore_threshold, stats_window, max_half_life, usd_per_trade,
			usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
			manage_exits, place_trades, abort_all_positions, max_positions,
			max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
			rebalance_interval_hours, position_timeout_hours, transaction_fee, slippage,
			starting_balance, candle_resolution, max_history_days, benchmark_symbol,
			risk_free_rate, initial_amount, usage_count, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		101,
		1,
		"Runtime Strategy",
		"Managed runtime strategy",
		"pairs_trading",
		false,
		false,
		"cointegration",
		1.5,
		21,
		24.0,
		10.0,
		100.0,
		true,
		true,
		true,
		true,
		false,
		5,
		15.0,
		2.0,
		5.0,
		1.0,
		24,
		72,
		0.0005,
		0.001,
		1000.0,
		"1HOUR",
		90,
		"BTC-USD",
		0.02,
		1000.0,
		0,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert strategy: %v", err)
	}

	keyService := services.NewKeyManagementService(repository.NewKeyRepository(dbConn))
	if _, err := keyService.CreateKey(1, "testnet", "0x1234567890123456789012345678901234567890", "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"); err != nil {
		t.Fatalf("seed dydx key: %v", err)
	}

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	RegisterStrategyRoutes(router, &db.Database{DB: dbConn})

	return router, dbConn, upstreamServer
}

func setupStrategyRuntimeRouter(t *testing.T, upstream http.Handler) (*gin.Engine, *sql.DB, *httptest.Server) {
	return setupStrategyRuntimeRouterWithExecutionStateSchema(t, upstream, false)
}

func loginStrategyRuntimeUser(t *testing.T, backendURL string) string {
	t.Helper()
	body, _ := json.Marshal(map[string]string{"username": "runtime-user", "password": "Pass123!"})
	resp, err := http.Post(backendURL+"/api/v1/auth/login", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected login status: %d", resp.StatusCode)
	}
	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	token, _ := payload["access_token"].(string)
	if token == "" {
		t.Fatal("missing access token")
	}
	return token
}

func TestStrategyRuntimeLifecycleRoutes(t *testing.T) {
	upstreamAuthHeaderCh := make(chan string, 16)
	upstreamCreatePayloadCh := make(chan map[string]interface{}, 1)

	var created bool
	status := "stopped"

	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"ready":true,"blockers":[],"warnings":[]}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		defer func() {
			if closeErr := r.Body.Close(); closeErr != nil {
				t.Errorf("close upstream request body: %v", closeErr)
			}
		}()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode upstream create payload: %v", err)
		}
		upstreamCreatePayloadCh <- payload
		created = true
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"strategy-1-101","status":"stopped"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		if !created {
			http.Error(w, `{"message":"not found"}`, http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(fmt.Sprintf(`{"success":true,"data":{"instance_id":"strategy-1-101","status":"%s","process_id":321,"config":{"trading_params":{"is_testnet":true}}}}`, status)))
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101/start", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		status = "running"
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"running"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101/stop", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		if got := r.URL.Query().Get("force"); got != "true" {
			t.Fatalf("expected force=true query, got %q", got)
		}
		status = "stopped"
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"stopped"}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	request := func(method, path string) map[string]interface{} {
		t.Helper()
		req, _ := http.NewRequest(method, backendServer.URL+path, nil)
		req.Header.Set("Authorization", "Bearer "+token)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("request %s %s failed: %v", method, path, err)
		}
		defer func() { _ = resp.Body.Close() }()
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			var payload map[string]interface{}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			t.Fatalf("unexpected status %d for %s %s: %v", resp.StatusCode, method, path, payload)
		}
		var payload map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
			t.Fatalf("decode response %s %s: %v", method, path, err)
		}
		return payload
	}

	startPayload := request(http.MethodPost, "/api/v1/strategies/101/start?network=testnet")
	runtimePayload := request(http.MethodGet, "/api/v1/strategies/101/runtime")
	stopPayload := request(http.MethodPost, "/api/v1/strategies/101/stop?force=true")

	startData := startPayload["data"].(map[string]interface{})
	if startData["status"] != "running" {
		t.Fatalf("expected running status after start, got %v", startData["status"])
	}
	if startData["instance_id"] != "strategy-1-101" {
		t.Fatalf("unexpected instance_id after start: %v", startData["instance_id"])
	}

	runtimeData := runtimePayload["data"].(map[string]interface{})
	if runtimeData["bot_status"] != "running" {
		t.Fatalf("expected runtime bot_status=running, got %v", runtimeData["bot_status"])
	}

	stopData := stopPayload["data"].(map[string]interface{})
	if stopData["status"] != "stopped" {
		t.Fatalf("expected stopped status after stop, got %v", stopData["status"])
	}

	select {
	case createPayload := <-upstreamCreatePayloadCh:
		if createPayload["instance_id"] != "strategy-1-101" {
			t.Fatalf("unexpected create payload instance_id: %v", createPayload["instance_id"])
		}
		tradingParams, _ := createPayload["trading_params"].(map[string]interface{})
		if tradingParams["is_testnet"] != true {
			t.Fatalf("expected testnet runtime payload, got %+v", tradingParams)
		}
		if tradingParams["strategy"] != "cointegration" {
			t.Fatalf("expected runtime strategy to be forwarded, got %+v", tradingParams)
		}
		if tradingParams["max_positions"] != float64(5) {
			t.Fatalf("expected live risk fields in trading payload, got %+v", tradingParams)
		}
		backtestingParams, _ := createPayload["backtesting_params"].(map[string]interface{})
		if backtestingParams["starting_balance"] != float64(1000) {
			t.Fatalf("expected backtesting defaults in create payload, got %+v", backtestingParams)
		}
		if backtestingParams["benchmark_symbol"] != "BTC-USD" {
			t.Fatalf("expected benchmark symbol in create payload, got %+v", backtestingParams)
		}
	default:
		t.Fatal("expected upstream create payload")
	}

	for i := 0; i < 3; i++ {
		select {
		case authHeader := <-upstreamAuthHeaderCh:
			if authHeader == "" {
				t.Fatal("expected upstream Authorization header to be forwarded")
			}
		case <-time.After(2 * time.Second):
			t.Fatal("timeout waiting for upstream auth header")
		}
	}
}

func TestStrategyRuntimeReadinessRoute(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST, got %s", r.Method)
		}
		defer func() { _ = r.Body.Close() }()
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode preflight payload: %v", err)
		}
		credentials, _ := payload["credentials"].(map[string]interface{})
		if got := credentials["chain_id"]; got != "dydx-testnet-4" {
			t.Fatalf("expected testnet chain_id, got %#v", got)
		}
		tradingParams, _ := payload["trading_params"].(map[string]interface{})
		if got := int(tradingParams["subaccount_number"].(float64)); got != 0 {
			t.Fatalf("expected subaccount 0, got %d", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"selected_runtime_network":"testnet","selected_subaccount":0,"wallet_ready":true,"account_exists":true,"available_collateral":250.0,"equity":250.0,"open_positions":0,"usd_per_trade":10.0,"usd_min_collateral":100.0,"capital_allocation_usd":1000.0,"trade_size_to_collateral_ratio":0.04,"sufficient_for_trade_size":true,"sufficient_for_min_collateral":true,"ready":true,"blockers":[],"warnings":[]}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/strategies/101/start-readiness?network=testnet", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("readiness request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected readiness status: %d", resp.StatusCode)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode readiness response: %v", err)
	}
	data, _ := payload["data"].(map[string]interface{})
	if ready, _ := data["ready"].(bool); !ready {
		t.Fatalf("expected readiness ready=true, got %#v", data["ready"])
	}
	if got, _ := data["selected_runtime_network"].(string); got != "testnet" {
		t.Fatalf("expected selected_runtime_network=testnet, got %q", got)
	}
	if _, ok := data["selected_subaccount"].(float64); !ok {
		t.Fatalf("expected selected_subaccount number in readiness payload, got %#v", data["selected_subaccount"])
	}
	if _, ok := data["blockers"].([]interface{}); !ok {
		t.Fatalf("expected blockers array in readiness payload, got %#v", data["blockers"])
	}
	if _, ok := data["warnings"].([]interface{}); !ok {
		t.Fatalf("expected warnings array in readiness payload, got %#v", data["warnings"])
	}
	if _, ok := data["available_collateral"].(float64); !ok {
		t.Fatalf("expected available_collateral number in readiness payload, got %#v", data["available_collateral"])
	}
}

func TestStrategyRuntimeStatusHandlesUnavailableUpstream(t *testing.T) {
	upstreamMux := http.NewServeMux()
	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()

	// Simulate the bot API being down after route wiring has captured its base URL.
	upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/strategies/101/runtime", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request runtime status: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode runtime payload: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected graceful 200 when upstream is unavailable, got %d payload=%v", resp.StatusCode, payload)
	}

	data, _ := payload["data"].(map[string]interface{})
	if data["status"] != "error" {
		t.Fatalf("expected error runtime status when upstream is unavailable, got %v", data["status"])
	}
	if data["bot_status"] != "unavailable" {
		t.Fatalf("expected bot_status=unavailable, got %v", data["bot_status"])
	}
}

func TestStrategyRuntimeStatusClearsStaleErrorWhenRemoteIsRunning(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"strategy-1-101","status":"running","process_id":777,"config":{"trading_params":{"is_testnet":true}}}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	if _, err := dbConn.Exec(
		`INSERT INTO strategy_execution_states (strategy_id, is_running, last_run_at, next_run_at, state, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		101,
		false,
		nil,
		nil,
		`{"instance_id":"strategy-1-101","status":"error","bot_status":"error","last_error":"runtime instance missing from bot API"}`,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("seed stale execution state: %v", err)
	}

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/strategies/101/runtime", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request runtime status: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected 200 for remote running runtime, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode runtime payload: %v", err)
	}

	data, _ := payload["data"].(map[string]interface{})
	if data["status"] != "running" {
		t.Fatalf("expected runtime status=running, got %v", data["status"])
	}
	if data["bot_status"] != "running" {
		t.Fatalf("expected runtime bot_status=running, got %v", data["bot_status"])
	}
	if value, exists := data["last_error"]; exists && value != "" && value != nil {
		t.Fatalf("expected stale runtime error to be cleared, got %v", value)
	}
}

func TestStrategyRuntimeStartRequiresActiveKey(t *testing.T) {
	upstreamMux := http.NewServeMux()
	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	if _, err := dbConn.Exec(`UPDATE dydx_keys SET is_active = 0`); err != nil {
		t.Fatalf("deactivate keys: %v", err)
	}

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start?network=testnet", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request start runtime: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusBadRequest {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected 400 when no key is configured, got %d payload=%v", resp.StatusCode, payload)
	}
}

func TestStrategyRuntimeStartRequiresExplicitNetworkSelection(t *testing.T) {
	upstreamMux := http.NewServeMux()
	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request start runtime without network: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusBadRequest {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected 400 when runtime network query is missing, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode missing-network response: %v", err)
	}
	if !strings.Contains(strings.ToLower(fmt.Sprintf("%v", payload["error"])), "network") {
		t.Fatalf("expected network-specific validation error, got %v", payload["error"])
	}
}

func TestStrategyRuntimeStartBlocksWhenReadinessFails(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"selected_runtime_network":"testnet","selected_subaccount":0,"wallet_ready":false,"account_exists":false,"available_collateral":0.0,"equity":0.0,"open_positions":0,"usd_per_trade":10.0,"usd_min_collateral":100.0,"capital_allocation_usd":1000.0,"trade_size_to_collateral_ratio":null,"sufficient_for_trade_size":false,"sufficient_for_min_collateral":false,"ready":false,"blockers":["No collateral available for the selected subaccount."],"warnings":[]}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start?network=testnet", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request readiness-gated start runtime: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusBadRequest {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected 400 when readiness fails, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode readiness failure response: %v", err)
	}
	if !strings.Contains(strings.ToLower(fmt.Sprintf("%v", payload["error"])), "readiness failed") {
		t.Fatalf("expected readiness failure in response error, got %v", payload["error"])
	}
}

func TestStrategyRuntimeGetRepairsLegacyExecutionStateSchema(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"strategy-1-101","status":"running","config":{"trading_params":{"is_testnet":true}}}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouterWithExecutionStateSchema(t, upstreamMux, true)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	if _, err := dbConn.Exec(
		`INSERT INTO strategy_execution_states (strategy_id, enabled, status, last_started, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)`,
		101,
		true,
		"running",
		time.Now().UTC(),
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("seed legacy execution state: %v", err)
	}

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/strategies/101/runtime", nil)
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request legacy runtime: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected 200 after legacy schema repair, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode runtime payload: %v", err)
	}

	data, _ := payload["data"].(map[string]interface{})
	if data["bot_status"] != "running" {
		t.Fatalf("expected repaired runtime bot_status to be running, got %v", data["bot_status"])
	}
	if data["is_running"] != true {
		t.Fatalf("expected repaired runtime is_running=true, got %v", data["is_running"])
	}
}

func TestStrategyRuntimeStartRequiresConfirmBeforeForceRecreate(t *testing.T) {
	var (
		createCalls int
		deleteCalls int
	)

	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"ready":true,"blockers":[],"warnings":[]}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			http.Error(w, `{"message":"not found"}`, http.StatusNotFound)
		case http.MethodDelete:
			deleteCalls++
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"success":true}`))
		default:
			t.Fatalf("unexpected method for runtime instance endpoint: %s", r.Method)
		}
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101/stop", func(w http.ResponseWriter, r *http.Request) {
		if got := r.URL.Query().Get("force"); got != "true" {
			t.Fatalf("expected force=true on recreate stop, got %q", got)
		}
		http.Error(w, `{"message":"not found"}`, http.StatusNotFound)
	})
	upstreamMux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, r *http.Request) {
		createCalls++
		if createCalls == 1 {
			http.Error(w, `{"message":"instance_id already exists: strategy-1-101"}`, http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"strategy-1-101","status":"stopped"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101/start", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"running"}}`))
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	if _, err := dbConn.Exec(
		`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, config, trading_params, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"strategy-1-101",
		"Runtime Strategy",
		1,
		"ERROR",
		"testnet",
		"cointegration",
		`{"strategy_id":101}`,
		`{"is_testnet":true}`,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("seed stale bot instance metadata: %v", err)
	}

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	firstReq, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start?network=testnet", nil)
	firstReq.Header.Set("Authorization", "Bearer "+token)
	firstResp, err := http.DefaultClient.Do(firstReq)
	if err != nil {
		t.Fatalf("request initial start runtime: %v", err)
	}
	defer func() { _ = firstResp.Body.Close() }()

	if firstResp.StatusCode != http.StatusConflict {
		var payload map[string]interface{}
		_ = json.NewDecoder(firstResp.Body).Decode(&payload)
		t.Fatalf("expected 409 conflict before recreate confirmation, got %d payload=%v", firstResp.StatusCode, payload)
	}

	var firstPayload map[string]interface{}
	if err := json.NewDecoder(firstResp.Body).Decode(&firstPayload); err != nil {
		t.Fatalf("decode initial conflict payload: %v", err)
	}
	if !strings.Contains(strings.ToLower(fmt.Sprintf("%v", firstPayload["error"])), "confirm recreate") {
		t.Fatalf("expected recreate confirmation hint, got %v", firstPayload["error"])
	}

	secondReq, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start?network=testnet&force_recreate=true", nil)
	secondReq.Header.Set("Authorization", "Bearer "+token)
	secondResp, err := http.DefaultClient.Do(secondReq)
	if err != nil {
		t.Fatalf("request force recreate runtime: %v", err)
	}
	defer func() { _ = secondResp.Body.Close() }()

	if secondResp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(secondResp.Body).Decode(&payload)
		t.Fatalf("expected 200 after force recreate, got %d payload=%v", secondResp.StatusCode, payload)
	}

	if createCalls != 2 {
		t.Fatalf("expected 2 upstream create attempts, got %d", createCalls)
	}
	if deleteCalls != 1 {
		t.Fatalf("expected 1 upstream delete during recreate, got %d", deleteCalls)
	}
}

func TestStrategyRuntimeStartMapsDuplicateInstanceMessageToConflict(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/runtime/preflight", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"ready":true,"blockers":[],"warnings":[]}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/strategy-1-101", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Fatalf("unexpected method for runtime instance endpoint: %s", r.Method)
		}
		http.Error(w, `{"message":"not found"}`, http.StatusNotFound)
	})
	upstreamMux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, `{"message":"instance_id already exists: strategy-1-101"}`, http.StatusBadRequest)
	})

	router, dbConn, upstreamServer := setupStrategyRuntimeRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginStrategyRuntimeUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start?network=testnet", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request duplicate-instance start runtime: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusConflict {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected 409 conflict for duplicate instance message, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode duplicate-instance conflict payload: %v", err)
	}
	if !strings.Contains(strings.ToLower(fmt.Sprintf("%v", payload["error"])), "confirm recreate") {
		t.Fatalf("expected confirm recreate guidance, got %v", payload["error"])
	}
}
