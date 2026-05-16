//go:build integration

package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupBotInstanceContractRouter(t *testing.T, upstream http.Handler) (*gin.Engine, *sql.DB, *httptest.Server) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	upstreamServer := httptest.NewServer(upstream)
	t.Setenv("BOT_API_URL", upstreamServer.URL)
	t.Setenv("APP_ENV", "test")

	const secret = "bot-instance-contract-lock-secret"
	t.Setenv("JWT_SECRET_KEY", secret)
	t.Setenv("BOT_API_TOKEN", "")
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "false")
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
	CREATE TABLE bot_instances (
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
	);`); err != nil {
		t.Fatalf("create bot_instances table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE bot_positions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		bot_instance_id INTEGER NOT NULL,
		position_id TEXT NOT NULL UNIQUE,
		market_1 TEXT,
		market_2 TEXT,
		status TEXT,
		is_active BOOLEAN,
		entry_timestamp DATETIME,
		entry_price_1 REAL,
		entry_price_2 REAL,
		entry_zscore REAL,
		side_1 TEXT,
		side_2 TEXT,
		size_1 REAL,
		size_2 REAL,
		hedge_ratio REAL,
		current_price_1 REAL,
		current_price_2 REAL,
		current_zscore REAL,
		unrealized_pnl REAL,
		unrealized_pnl_pct REAL,
		exit_timestamp DATETIME,
		exit_price_1 REAL,
		exit_price_2 REAL,
		exit_zscore REAL,
		realized_pnl REAL,
		realized_pnl_pct REAL,
		duration_hours REAL,
		created_at DATETIME,
		updated_at DATETIME
	);`); err != nil {
		t.Fatalf("create bot_positions table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE bot_trades (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		bot_instance_id INTEGER NOT NULL,
		trade_id TEXT NOT NULL UNIQUE,
		market_1 TEXT,
		market_2 TEXT,
		entry_timestamp DATETIME,
		entry_price_1 REAL,
		entry_price_2 REAL,
		entry_zscore REAL,
		side_1 TEXT,
		side_2 TEXT,
		size_1 REAL,
		size_2 REAL,
		hedge_ratio REAL,
		exit_timestamp DATETIME,
		exit_price_1 REAL,
		exit_price_2 REAL,
		exit_zscore REAL,
		pnl REAL,
		pnl_pct REAL,
		duration_hours REAL,
		strategy_zscore_threshold REAL,
		created_at DATETIME,
		updated_at DATETIME
	);`); err != nil {
		t.Fatalf("create bot_trades table: %v", err)
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

	if _, err := dbConn.Exec(
		`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, config, trading_params, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"123",
		"seed-bot",
		1,
		"STOPPED",
		"testnet",
		"default",
		`{}`,
		`{}`,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert seed bot instance: %v", err)
	}

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	RegisterBotInstanceRoutes(router, &db.Database{DB: dbConn}, nil)

	return router, dbConn, upstreamServer
}

func loginBotInstanceContractUser(t *testing.T, backendURL string) string {
	t.Helper()
	body, _ := json.Marshal(map[string]string{"username": "smoke-user", "password": "Pass123!"})
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

func TestContractLock_BotLifecycleEndpointsStableEnvelope(t *testing.T) {
	stopForceQuery := make(chan string, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"new-456"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123/start", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"running"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123/stop", func(w http.ResponseWriter, r *http.Request) {
		stopForceQuery <- r.URL.Query().Get("force")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"stopped"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123/restart", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"running"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true}`))
	})

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	request := func(method, path string, body []byte) map[string]interface{} {
		t.Helper()
		req, _ := http.NewRequest(method, backendServer.URL+path, bytes.NewReader(body))
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("Content-Type", "application/json")
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("request %s %s failed: %v", method, path, err)
		}
		defer func() { _ = resp.Body.Close() }()
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			t.Fatalf("unexpected status %d for %s %s", resp.StatusCode, method, path)
		}
		var payload map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
			t.Fatalf("decode response %s %s: %v", method, path, err)
		}
		if _, ok := payload["success"].(bool); !ok {
			t.Fatalf("missing success bool for %s %s: %v", method, path, payload)
		}
		if _, ok := payload["timestamp"].(string); !ok {
			t.Fatalf("missing timestamp string for %s %s: %v", method, path, payload)
		}
		if _, ok := payload["data"]; !ok {
			t.Fatalf("missing data for %s %s: %v", method, path, payload)
		}
		return payload
	}

	request(http.MethodGet, "/api/v1/bots", nil)
	request(http.MethodGet, "/api/v1/bots/123", nil)

	createBody, _ := json.Marshal(map[string]interface{}{
		"instance_id":   "new-456",
		"instance_name": "new-bot",
		"credentials": map[string]interface{}{
			"address":  "0x1234567890123456789012345678901234567890",
			"mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
		},
		"trading_params": map[string]interface{}{
			"is_testnet": true,
		},
	})
	request(http.MethodPost, "/api/v1/bots", createBody)
	request(http.MethodPost, "/api/v1/bots/123/start", nil)
	stopPayload := request(http.MethodPost, "/api/v1/bots/123/stop?force=true", nil)
	request(http.MethodPost, "/api/v1/bots/123/restart", nil)
	request(http.MethodDelete, "/api/v1/bots/123", nil)

	if data, ok := stopPayload["data"].(map[string]interface{}); ok {
		if data["force"] != true {
			t.Fatalf("expected stop response data.force=true, got %v", data["force"])
		}
	} else {
		t.Fatalf("expected stop data object, got %T", stopPayload["data"])
	}

	select {
	case forceValue := <-stopForceQuery:
		if forceValue != "true" {
			t.Fatalf("expected upstream stop query force=true, got %q", forceValue)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream stop force query")
	}
}

func TestContractLock_BotTradesStatusQueryAndPayloadShape(t *testing.T) {
	tradesQuery := make(chan string, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/123/trades", func(w http.ResponseWriter, r *http.Request) {
		tradesQuery <- r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"instance_id":"123","total_trades":0,"filter_status":"OPEN","trades":[]},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123/stats", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"instance_id":"123","bot_statistics":{},"trade_statistics":{}},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/trades?status=OPEN&limit=5&winning_only=true", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("trades request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected trades status 200, got %d", resp.StatusCode)
	}
	var tradesPayload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&tradesPayload); err != nil {
		t.Fatalf("decode trades response: %v", err)
	}
	if _, ok := tradesPayload["success"].(bool); !ok {
		t.Fatalf("expected trades success bool, got %v", tradesPayload)
	}
	data, ok := tradesPayload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected trades data object, got %T", tradesPayload["data"])
	}
	for _, key := range []string{"instance_id", "total_trades", "trades"} {
		if _, exists := data[key]; !exists {
			t.Fatalf("missing trades data key %q in payload: %v", key, data)
		}
	}

	select {
	case rawQuery := <-tradesQuery:
		if rawQuery != "status=OPEN" {
			t.Fatalf("expected upstream trades query to forward only status=OPEN, got %q", rawQuery)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream trades query")
	}

	statsReq, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/stats", nil)
	statsReq.Header.Set("Authorization", "Bearer "+token)
	statsResp, err := http.DefaultClient.Do(statsReq)
	if err != nil {
		t.Fatalf("stats request failed: %v", err)
	}
	defer func() { _ = statsResp.Body.Close() }()
	if statsResp.StatusCode != http.StatusOK {
		t.Fatalf("expected stats status 200, got %d", statsResp.StatusCode)
	}
	var statsPayload map[string]interface{}
	if err := json.NewDecoder(statsResp.Body).Decode(&statsPayload); err != nil {
		t.Fatalf("decode stats response: %v", err)
	}
	statsData, ok := statsPayload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected stats data object, got %T", statsPayload["data"])
	}
	for _, key := range []string{"success", "message", "data", "timestamp"} {
		if _, exists := statsData[key]; !exists {
			t.Fatalf("missing stats delegated envelope key %q in payload: %v", key, statsData)
		}
	}
}

func TestContractLock_BotPositionsEndpointStableEnvelope(t *testing.T) {
	upstreamMux := http.NewServeMux()

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	var botID int
	if err := dbConn.QueryRow(`SELECT id FROM bot_instances WHERE instance_id = ?`, "123").Scan(&botID); err != nil {
		t.Fatalf("query seed bot instance id: %v", err)
	}

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO bot_positions (bot_instance_id, position_id, market_1, market_2, status, is_active, entry_timestamp, entry_price_1, entry_price_2, entry_zscore, side_1, side_2, size_1, size_2, hedge_ratio, current_price_1, current_price_2, current_zscore, unrealized_pnl, unrealized_pnl_pct, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		botID,
		"pos-1",
		"BTC-USD",
		"ETH-USD",
		"open",
		true,
		now,
		100.0,
		200.0,
		1.2,
		"buy",
		"sell",
		0.1,
		0.2,
		1.0,
		101.0,
		201.0,
		1.1,
		3.5,
		0.8,
		now,
		now,
	); err != nil {
		t.Fatalf("insert bot position: %v", err)
	}

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/positions?status=open", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("positions request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected positions status 200, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode positions response: %v", err)
	}
	if _, ok := payload["success"].(bool); !ok {
		t.Fatalf("expected success bool in positions payload: %v", payload)
	}
	if _, ok := payload["timestamp"].(string); !ok {
		t.Fatalf("expected timestamp in positions payload: %v", payload)
	}

	positions, ok := payload["data"].([]interface{})
	if !ok {
		t.Fatalf("expected positions data array, got %T", payload["data"])
	}
	if len(positions) != 1 {
		t.Fatalf("expected one position, got %d", len(positions))
	}
	position, ok := positions[0].(map[string]interface{})
	if !ok {
		t.Fatalf("expected position object, got %T", positions[0])
	}
	if position["position_id"] != "pos-1" {
		t.Fatalf("expected position_id pos-1, got %v", position["position_id"])
	}
	if position["status"] != "open" {
		t.Fatalf("expected status open, got %v", position["status"])
	}
}

func TestContractLock_BotTradeEndpointScopedToInstance(t *testing.T) {
	upstreamMux := http.NewServeMux()

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO bot_instances (instance_id, instance_name, user_id, status, network, strategy, config, trading_params, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"456",
		"other-bot",
		1,
		"STOPPED",
		"testnet",
		"default",
		`{}`,
		`{}`,
		now,
		now,
	); err != nil {
		t.Fatalf("insert second bot instance: %v", err)
	}

	var botID, otherBotID int
	if err := dbConn.QueryRow(`SELECT id FROM bot_instances WHERE instance_id = ?`, "123").Scan(&botID); err != nil {
		t.Fatalf("query seed bot instance id: %v", err)
	}
	if err := dbConn.QueryRow(`SELECT id FROM bot_instances WHERE instance_id = ?`, "456").Scan(&otherBotID); err != nil {
		t.Fatalf("query second bot instance id: %v", err)
	}

	if _, err := dbConn.Exec(
		`INSERT INTO bot_trades (bot_instance_id, trade_id, market_1, market_2, entry_timestamp, entry_price_1, entry_price_2, entry_zscore, side_1, side_2, size_1, size_2, hedge_ratio, pnl, pnl_pct, duration_hours, strategy_zscore_threshold, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		botID,
		"trade-1",
		"BTC-USD",
		"ETH-USD",
		now,
		100.0,
		200.0,
		1.0,
		"buy",
		"sell",
		0.1,
		0.2,
		1.0,
		2.5,
		1.5,
		1.2,
		2.0,
		now,
		now,
	); err != nil {
		t.Fatalf("insert bot trade for seed instance: %v", err)
	}

	if _, err := dbConn.Exec(
		`INSERT INTO bot_trades (bot_instance_id, trade_id, market_1, market_2, entry_timestamp, entry_price_1, entry_price_2, entry_zscore, side_1, side_2, size_1, size_2, hedge_ratio, pnl, pnl_pct, duration_hours, strategy_zscore_threshold, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		otherBotID,
		"trade-2",
		"SOL-USD",
		"ADA-USD",
		now,
		50.0,
		25.0,
		0.8,
		"buy",
		"sell",
		0.3,
		0.4,
		1.0,
		1.0,
		0.5,
		0.9,
		1.5,
		now,
		now,
	); err != nil {
		t.Fatalf("insert bot trade for other instance: %v", err)
	}

	t.Run("returns trade when scoped to instance", func(t *testing.T) {
		req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/trades/trade-1", nil)
		req.Header.Set("Authorization", "Bearer "+token)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("trade request failed: %v", err)
		}
		defer func() { _ = resp.Body.Close() }()
		if resp.StatusCode != http.StatusOK {
			var payload map[string]interface{}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			t.Fatalf("expected trade status 200, got %d payload=%v", resp.StatusCode, payload)
		}

		var payload map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
			t.Fatalf("decode trade response: %v", err)
		}
		if _, ok := payload["timestamp"].(string); !ok {
			t.Fatalf("expected timestamp in trade payload: %v", payload)
		}
		trade, ok := payload["data"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected trade object, got %T", payload["data"])
		}
		if trade["trade_id"] != "trade-1" {
			t.Fatalf("expected trade_id trade-1, got %v", trade["trade_id"])
		}
	})

	t.Run("returns not found for mismatched instance", func(t *testing.T) {
		req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/trades/trade-2", nil)
		req.Header.Set("Authorization", "Bearer "+token)
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("trade scope mismatch request failed: %v", err)
		}
		defer func() { _ = resp.Body.Close() }()
		if resp.StatusCode != http.StatusNotFound {
			var payload map[string]interface{}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			t.Fatalf("expected trade mismatch status 404, got %d payload=%v", resp.StatusCode, payload)
		}

		var payload map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
			t.Fatalf("decode trade mismatch response: %v", err)
		}
		if success, ok := payload["success"].(bool); !ok || success {
			t.Fatalf("expected success=false for mismatch payload: %v", payload)
		}
	})
}

func TestContractLock_BotSummaryStatsOnlyStableEnvelope(t *testing.T) {
	statsQuery := make(chan string, 1)
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/123/stats", func(w http.ResponseWriter, r *http.Request) {
		statsQuery <- r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"instance_id":"123","bot_statistics":{"total_trades":2},"trade_statistics":{"total_trades":2,"win_rate":0.5}},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/summary?include=stats&limit=5", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("summary request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected summary status 200, got %d payload=%v", resp.StatusCode, payload)
	}

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode summary response: %v", err)
	}

	if _, ok := payload["success"].(bool); !ok {
		t.Fatalf("expected success bool in summary payload: %v", payload)
	}
	if _, ok := payload["timestamp"].(string); !ok {
		t.Fatalf("expected timestamp in summary payload: %v", payload)
	}

	data, ok := payload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected summary data object, got %T", payload["data"])
	}
	if data["instance_id"] != "123" {
		t.Fatalf("expected summary instance_id=123, got %v", data["instance_id"])
	}
	if _, ok := data["generated_at"].(string); !ok {
		t.Fatalf("expected generated_at in summary payload data: %v", data)
	}
	stats, ok := data["stats"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected stats object in summary payload data, got %T", data["stats"])
	}
	statsPayload := stats
	if nested, ok := stats["data"].(map[string]interface{}); ok {
		statsPayload = nested
	}
	if _, ok := statsPayload["bot_statistics"].(map[string]interface{}); !ok {
		t.Fatalf("expected stats payload bot_statistics object, got %T", statsPayload["bot_statistics"])
	}
	if _, exists := data["positions"]; exists {
		t.Fatalf("did not expect positions when include=stats, got %v", data["positions"])
	}
	if _, exists := data["trades"]; exists {
		t.Fatalf("did not expect trades when include=stats, got %v", data["trades"])
	}

	select {
	case rawQuery := <-statsQuery:
		if rawQuery != "" {
			t.Fatalf("expected upstream stats query to remain empty, got %q", rawQuery)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream summary stats call")
	}
}

func TestContractLock_BotStatsMissingUpstreamReturnsEmptyPayload(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/123/stats", func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, `{"message":"Bot instance '123' not found"}`, http.StatusNotFound)
	})

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	statsReq, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/bots/123/stats", nil)
	statsReq.Header.Set("Authorization", "Bearer "+token)
	statsResp, err := http.DefaultClient.Do(statsReq)
	if err != nil {
		t.Fatalf("stats request failed: %v", err)
	}
	defer func() { _ = statsResp.Body.Close() }()
	if statsResp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(statsResp.Body).Decode(&payload)
		t.Fatalf("expected stats status 200 for recoverable upstream miss, got %d payload=%v", statsResp.StatusCode, payload)
	}

	var statsPayload map[string]interface{}
	if err := json.NewDecoder(statsResp.Body).Decode(&statsPayload); err != nil {
		t.Fatalf("decode stats response: %v", err)
	}
	statsData, ok := statsPayload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected stats data object, got %T", statsPayload["data"])
	}
	if statsData["instance_id"] != "123" {
		t.Fatalf("expected instance_id=123, got %v", statsData["instance_id"])
	}
	if statsData["degraded"] != true {
		t.Fatalf("expected degraded=true, got %v", statsData["degraded"])
	}
	if _, ok := statsData["bot_statistics"].(map[string]interface{}); !ok {
		t.Fatalf("expected bot_statistics object, got %T", statsData["bot_statistics"])
	}
	if _, ok := statsData["trade_statistics"].(map[string]interface{}); !ok {
		t.Fatalf("expected trade_statistics object, got %T", statsData["trade_statistics"])
	}

	var status string
	var errorMessage sql.NullString
	if err := dbConn.QueryRow(
		`SELECT status, error_message FROM bot_instances WHERE instance_id = ?`,
		"123",
	).Scan(&status, &errorMessage); err != nil {
		t.Fatalf("query reconciled bot instance: %v", err)
	}
	if status != "ERROR" {
		t.Fatalf("expected local bot status ERROR after recoverable upstream miss, got %q", status)
	}
	if !errorMessage.Valid || errorMessage.String != "runtime instance missing from bot API" {
		t.Fatalf("expected reconciled error message, got %#v", errorMessage)
	}
}

func TestContractLock_BotRestartRecoversMissingUpstreamInstance(t *testing.T) {
	var (
		createCalls  int
		startCalls   int
		restartCalls int
		remoteExists bool
	)

	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/123", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			if !remoteExists {
				http.Error(w, `{"message":"Bot instance '123' not found"}`, http.StatusNotFound)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"123","status":"stopped"}}`))
			return
		}
		http.NotFound(w, r)
	})
	upstreamMux.HandleFunc("/api/v1/bots", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.NotFound(w, r)
			return
		}
		createCalls++
		var payload map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode create payload: %v", err)
		}
		if payload["instance_id"] != "123" {
			t.Fatalf("expected recovered create payload instance_id=123, got %v", payload["instance_id"])
		}
		remoteExists = true
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"instance_id":"123","status":"stopped"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123/start", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.NotFound(w, r)
			return
		}
		startCalls++
		if !remoteExists {
			http.Error(w, `{"message":"Instance 123 not found"}`, http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"data":{"status":"running"}}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/123/restart", func(w http.ResponseWriter, r *http.Request) {
		restartCalls++
		http.Error(w, `{"message":"unexpected restart"}`, http.StatusBadRequest)
	})

	router, dbConn, upstreamServer := setupBotInstanceContractRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	defer upstreamServer.Close()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginBotInstanceContractUser(t, backendServer.URL)

	req, _ := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/bots/123/restart", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("restart request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		var payload map[string]interface{}
		_ = json.NewDecoder(resp.Body).Decode(&payload)
		t.Fatalf("expected restart status 200, got %d payload=%v", resp.StatusCode, payload)
	}

	if createCalls != 1 {
		t.Fatalf("expected one upstream create call, got %d", createCalls)
	}
	if startCalls != 2 {
		t.Fatalf("expected two upstream start calls (initial miss + recovered retry), got %d", startCalls)
	}
	if restartCalls != 0 {
		t.Fatalf("expected no direct upstream restart call during recovery, got %d", restartCalls)
	}

	var status string
	if err := dbConn.QueryRow(
		`SELECT status FROM bot_instances WHERE instance_id = ?`,
		"123",
	).Scan(&status); err != nil {
		t.Fatalf("query restarted bot instance: %v", err)
	}
	if status != "RUNNING" {
		t.Fatalf("expected local bot status RUNNING after recovery restart, got %q", status)
	}
}

func TestContractLock_DelegatedBotPayloadRequiredKeys(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/bots/hist-1/history", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"instance_id":"hist-1","total_events":0,"events":[]},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/101/market-data", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"bot_instance_id":101,"market_data":[],"count":0},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/101/realtime-stats", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"bot_instance_id":101,"stats":{}},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/bots/101/alerts", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"bot_instance_id":101,"alerts":[],"count":0},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()
	token := loginDelegatedBacktestTestUser(t, backendServer.URL)

	type endpointCheck struct {
		path         string
		requiredKeys []string
	}
	checks := []endpointCheck{
		{path: "/api/v1/bots/hist-1/history?days=3", requiredKeys: []string{"instance_id", "total_events", "events"}},
		{path: "/api/v1/bots/101/market-data", requiredKeys: []string{"bot_instance_id", "market_data", "count"}},
		{path: "/api/v1/bots/101/realtime-stats", requiredKeys: []string{"bot_instance_id", "stats"}},
		{path: "/api/v1/bots/101/alerts?limit=10", requiredKeys: []string{"bot_instance_id", "alerts", "count"}},
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

		if _, ok := payload["success"].(bool); !ok {
			t.Fatalf("expected success bool for %s payload: %v", check.path, payload)
		}
		if _, ok := payload["message"].(string); !ok {
			t.Fatalf("expected message string for %s payload: %v", check.path, payload)
		}
		if _, ok := payload["timestamp"].(string); !ok {
			t.Fatalf("expected timestamp string for %s payload: %v", check.path, payload)
		}
		data, ok := payload["data"].(map[string]interface{})
		if !ok {
			t.Fatalf("expected data object for %s payload: %v", check.path, payload)
		}
		for _, key := range check.requiredKeys {
			if _, exists := data[key]; !exists {
				t.Fatalf("missing data.%s for %s payload: %v", key, check.path, data)
			}
		}
	}
}
