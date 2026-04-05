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
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupStrategyRuntimeRouter(t *testing.T, upstream http.Handler) (*gin.Engine, *sql.DB, *httptest.Server) {
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

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}

	schema := []string{
		`CREATE TABLE users (
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
		);`,
		`CREATE TABLE backtest_strategies (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			name TEXT NOT NULL,
			description TEXT,
			category TEXT,
			is_public BOOLEAN NOT NULL DEFAULT 0,
			is_default BOOLEAN NOT NULL DEFAULT 0,
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
			is_running BOOLEAN NOT NULL DEFAULT 0,
			last_run_at DATETIME,
			next_run_at DATETIME,
			state TEXT,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL
		);`,
		`CREATE TABLE dydx_keys (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			network TEXT NOT NULL,
			chain_address TEXT NOT NULL,
			encrypted_secret TEXT NOT NULL,
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
			zscore_threshold, stats_window, max_half_life, usd_per_trade,
			usd_min_collateral, close_at_zscore_cross, find_cointegrated_pairs,
			manage_exits, place_trades, abort_all_positions, max_positions,
			max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct,
			rebalance_interval_hours, position_timeout_hours, transaction_fee, slippage,
			starting_balance, candle_resolution, max_history_days, benchmark_symbol,
			risk_free_rate, initial_amount, usage_count, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		101,
		1,
		"Runtime Strategy",
		"Managed runtime strategy",
		"pairs_trading",
		false,
		false,
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
	upstreamMux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		defer r.Body.Close()
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

	startPayload := request(http.MethodPost, "/api/v1/strategies/101/start")
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

	req, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/strategies/101/start", nil)
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
