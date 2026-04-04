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
	RegisterBotInstanceRoutes(router, &db.Database{DB: dbConn})

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

