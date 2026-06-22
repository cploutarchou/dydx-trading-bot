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

	"github.com/gorilla/websocket"
	"golang.org/x/crypto/bcrypt"
)

func seedDelegatedBacktestTestUser(t *testing.T, dbConn *sql.DB, username, password string, isAdmin bool) {
	t.Helper()

	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate password hash: %v", err)
	}

	role := "client"
	if isAdmin {
		role = "admin"
	}

	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		username,
		fmt.Sprintf("%s@example.local", username),
		role,
		username,
		"",
		string(hash),
		true,
		isAdmin,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert user %s: %v", username, err)
	}
}

func loginDelegatedBacktestTestCredentials(t *testing.T, backendURL, username, password string) string {
	t.Helper()

	loginBody, _ := json.Marshal(map[string]string{
		"username": username,
		"password": password,
	})
	loginResp, err := http.Post(
		fmt.Sprintf("%s/api/v1/auth/login", backendURL),
		"application/json",
		bytes.NewReader(loginBody),
	)
	if err != nil {
		t.Fatalf("login request for %s: %v", username, err)
	}
	defer func() { _ = loginResp.Body.Close() }()

	if loginResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected login status for %s: %d", username, loginResp.StatusCode)
	}

	var tokenResp struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(loginResp.Body).Decode(&tokenResp); err != nil {
		t.Fatalf("decode login response for %s: %v", username, err)
	}
	if tokenResp.AccessToken == "" {
		t.Fatalf("missing access token for %s", username)
	}

	return tokenResp.AccessToken
}

func authenticatedJSONRequest(t *testing.T, method, url, token string) (int, map[string]interface{}) {
	t.Helper()

	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		t.Fatalf("build request %s %s: %v", method, url, err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request %s %s: %v", method, url, err)
	}
	defer func() { _ = resp.Body.Close() }()

	var payload map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		t.Fatalf("decode response %s %s: %v", method, url, err)
	}

	return resp.StatusCode, payload
}

func TestDelegateCapabilitiesAndRuntimeDBConfigRoutes(t *testing.T) {
	capabilitiesAuthHeader := make(chan string, 1)
	runtimeAuthHeader := make(chan string, 1)
	arbitrageMetricsAuthHeader := make(chan string, 1)
	arbitragePriorityQuery := make(chan string, 1)
	arbitrageExplainPath := make(chan string, 1)

	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/capabilities", func(w http.ResponseWriter, r *http.Request) {
		capabilitiesAuthHeader <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"service":"bot","http_endpoints":["GET /api/v1/bots"],"websocket_channels":["WS /ws/strategies"],"http_count":1,"websocket_count":1,"count":2},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/runtime/db-config", func(w http.ResponseWriter, r *http.Request) {
		runtimeAuthHeader <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"db_type":"postgres","cutover_mode":"dedicated","connection_source":"BOT_DATABASE_URL","count":1},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/arbitrage/improvement-metrics", func(w http.ResponseWriter, r *http.Request) {
		arbitrageMetricsAuthHeader <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"counters":{"exchange_api_calls_saved_total":2},"rejection_reasons":{"min_order_size":3,"market_already_open":1},"feature_flags":{"PAIR_PRIORITY_ENGINE_ENABLED":false}},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/arbitrage/pair-priority", func(w http.ResponseWriter, r *http.Request) {
		arbitragePriorityQuery <- r.URL.Query().Get("limit")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"pairs":[{"pair":"ETH-USD/BTC-USD","score":1.25,"explanation":["confidence=0.900"]}],"count":1,"enabled":false},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/arbitrage/opportunity/reason_min_order_size/explain", func(w http.ResponseWriter, r *http.Request) {
		arbitrageExplainPath <- r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"opportunity_id":"reason_min_order_size","matched_rejection_reason":{"reason":"min_order_size","count":3},"top_rejection_reasons":[{"reason":"min_order_size","count":3}],"explainability_scope":"runtime_diagnostics"},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	seedDelegatedBacktestTestUser(t, dbConn, "admin-user", "AdminPass123!", true)

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	userToken := loginDelegatedBacktestTestCredentials(t, backendServer.URL, "smoke-user", "Pass123!")
	adminToken := loginDelegatedBacktestTestCredentials(t, backendServer.URL, "admin-user", "AdminPass123!")

	statusCode, payload := authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/capabilities", userToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected capabilities status: %d", statusCode)
	}
	data, _ := payload["data"].(map[string]interface{})
	if data["service"] != "bot" {
		t.Fatalf("expected service=bot, got %v", data["service"])
	}

	select {
	case authHeader := <-capabilitiesAuthHeader:
		if authHeader == "" {
			t.Fatal("missing upstream capabilities Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for capabilities upstream auth header")
	}

	statusCode, payload = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/runtime/db-config", userToken)
	if statusCode != http.StatusForbidden {
		t.Fatalf("expected non-admin runtime db-config status 403, got %d", statusCode)
	}
	if payload["message"] != "admin access required" {
		t.Fatalf("unexpected non-admin runtime db-config message: %v", payload["message"])
	}

	statusCode, payload = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/runtime/db-config", adminToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected admin runtime db-config status: %d", statusCode)
	}
	data, _ = payload["data"].(map[string]interface{})

	supportedDBs := map[string]bool{"postgres": true, "postgresql": true}
	dbType, ok := data["db_type"].(string)
	if !ok || !supportedDBs[dbType] {
		t.Fatalf("expected supported db_type (postgres/postgresql), got %v", data["db_type"])
	}

	select {
	case authHeader := <-runtimeAuthHeader:
		if authHeader == "" {
			t.Fatal("missing upstream runtime db-config Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for runtime db-config upstream auth header")
	}

	statusCode, payload = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/arbitrage/improvement-metrics", userToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected arbitrage metrics status: %d", statusCode)
	}
	data, _ = payload["data"].(map[string]interface{})
	if _, ok := data["counters"]; !ok {
		t.Fatalf("expected counters in arbitrage metrics payload: %v", payload)
	}
	if _, ok := data["rejection_reasons"]; !ok {
		t.Fatalf("expected rejection_reasons in arbitrage metrics payload: %v", payload)
	}

	select {
	case authHeader := <-arbitrageMetricsAuthHeader:
		if authHeader == "" {
			t.Fatal("missing upstream arbitrage metrics Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for arbitrage metrics upstream auth header")
	}

	statusCode, payload = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/arbitrage/pair-priority?limit=7", userToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected arbitrage pair-priority status: %d", statusCode)
	}
	data, _ = payload["data"].(map[string]interface{})
	if _, ok := data["pairs"]; !ok {
		t.Fatalf("expected pairs in arbitrage priority payload: %v", payload)
	}

	select {
	case limit := <-arbitragePriorityQuery:
		if limit != "7" {
			t.Fatalf("expected priority limit=7 upstream, got %q", limit)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for arbitrage priority query")
	}

	statusCode, payload = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/arbitrage/opportunity/reason_min_order_size/explain", userToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected arbitrage explain status: %d", statusCode)
	}
	data, _ = payload["data"].(map[string]interface{})
	if data["opportunity_id"] != "reason_min_order_size" {
		t.Fatalf("expected opportunity_id=reason_min_order_size, got %v", data["opportunity_id"])
	}
	if _, ok := data["top_rejection_reasons"]; !ok {
		t.Fatalf("expected top_rejection_reasons in arbitrage explain payload: %v", payload)
	}

	select {
	case path := <-arbitrageExplainPath:
		if path != "/api/v1/arbitrage/opportunity/reason_min_order_size/explain" {
			t.Fatalf("unexpected arbitrage explain upstream path: %q", path)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for arbitrage explain path")
	}
}

func TestDelegateInterruptedBacktestsRoutes(t *testing.T) {
	limitQuery := make(chan string, 1)
	dryRunQuery := make(chan string, 1)
	adminDryRunQuery := make(chan string, 1)
	repairDryRunQuery := make(chan string, 1)

	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/interrupted", func(w http.ResponseWriter, r *http.Request) {
		limitQuery <- r.URL.Query().Get("limit")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"interruption_error":"restart","orphaned_in_progress":[],"interrupted_runs":[{"run_id":"run-1","status":"failed"}],"orphaned_count":0,"interrupted_count":1,"count":1},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/interrupted/reconcile", func(w http.ResponseWriter, r *http.Request) {
		dryRunQuery <- r.URL.Query().Get("dry_run")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"interruption_error":"restart","dry_run":false,"candidates":[{"run_id":"run-1"}],"reconciled":[{"run_id":"run-1"}],"candidate_count":1,"reconciled_count":1,"count":1},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/admin/backtests/interrupted", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"interruption_error":"restart","orphaned_in_progress":[],"interrupted_runs":[],"orphaned_count":0,"interrupted_count":0,"count":0},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/admin/backtests/interrupted/reconcile", func(w http.ResponseWriter, r *http.Request) {
		adminDryRunQuery <- r.URL.Query().Get("dry_run")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"interruption_error":"restart","dry_run":true,"candidates":[],"reconciled":[],"candidate_count":0,"reconciled_count":0,"count":0},"timestamp":"2026-04-04T00:00:00Z"}`))
	})
	upstreamMux.HandleFunc("/api/v1/admin/backtests/run-1/repair-request", func(w http.ResponseWriter, r *http.Request) {
		repairDryRunQuery <- r.URL.Query().Get("dry_run")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"run_id":"run-1","request_available":true,"repaired":true,"dry_run":false},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	seedDelegatedBacktestTestUser(t, dbConn, "admin-user", "AdminPass123!", true)

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	userToken := loginDelegatedBacktestTestCredentials(t, backendServer.URL, "smoke-user", "Pass123!")
	adminToken := loginDelegatedBacktestTestCredentials(t, backendServer.URL, "admin-user", "AdminPass123!")

	statusCode, payload := authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/backtests/interrupted?limit=25", userToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected interrupted status: %d", statusCode)
	}
	data, _ := payload["data"].(map[string]interface{})
	if _, ok := data["interrupted_runs"]; !ok {
		t.Fatalf("expected interrupted_runs in payload: %v", payload)
	}

	select {
	case limit := <-limitQuery:
		if limit != "25" {
			t.Fatalf("expected limit=25 upstream, got %q", limit)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for interrupted limit query")
	}

	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/interrupted/reconcile?dry_run=false", nil)
	if err != nil {
		t.Fatalf("build reconcile request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+userToken)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("reconcile request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected reconcile status: %d", resp.StatusCode)
	}

	select {
	case dryRun := <-dryRunQuery:
		if dryRun != "false" {
			t.Fatalf("expected dry_run=false upstream, got %q", dryRun)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for reconcile dry_run query")
	}

	statusCode, _ = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/admin/backtests/interrupted", userToken)
	if statusCode != http.StatusForbidden {
		t.Fatalf("expected non-admin admin-alias status 403, got %d", statusCode)
	}
	if payload["message"] != "admin access required" {
		t.Fatalf("unexpected admin alias forbidden message: %v", payload["message"])
	}

	statusCode, _ = authenticatedJSONRequest(t, http.MethodGet, backendServer.URL+"/api/v1/admin/backtests/interrupted", adminToken)
	if statusCode != http.StatusOK {
		t.Fatalf("unexpected admin interrupted status: %d", statusCode)
	}

	req, err = http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/admin/backtests/interrupted/reconcile", nil)
	if err != nil {
		t.Fatalf("build admin reconcile request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+adminToken)
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("admin reconcile request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected admin reconcile status: %d", resp.StatusCode)
	}

	select {
	case dryRun := <-adminDryRunQuery:
		if dryRun != "true" {
			t.Fatalf("expected admin dry_run=true upstream, got %q", dryRun)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for admin reconcile dry_run query")
	}

	req, err = http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/admin/backtests/run-1/repair-request?dry_run=false", nil)
	if err != nil {
		t.Fatalf("build admin repair request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+adminToken)
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("admin repair request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected admin repair status: %d", resp.StatusCode)
	}

	select {
	case dryRun := <-repairDryRunQuery:
		if dryRun != "false" {
			t.Fatalf("expected repair dry_run=false upstream, got %q", dryRun)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for repair dry_run query")
	}
}

func TestSmoke_AliasWebSocketProxyRoutes(t *testing.T) {
	backtestAuthHeaderCh := make(chan string, 1)
	botAuthHeaderCh := make(chan string, 1)
	upgrader := websocket.Upgrader{CheckOrigin: func(_ *http.Request) bool { return true }}

	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/ws/backtests/alias-run", func(w http.ResponseWriter, r *http.Request) {
		backtestAuthHeaderCh <- r.Header.Get("Authorization")
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer closeWebSocketConn(t, conn, "upstream alias backtest")

		payload, _ := json.Marshal(map[string]interface{}{
			"type":   "backtest_progress",
			"run_id": "alias-run",
		})
		_ = conn.WriteMessage(websocket.TextMessage, payload)
		time.Sleep(100 * time.Millisecond)
	})
	upstreamMux.HandleFunc("/ws/bots/bot-123", func(w http.ResponseWriter, r *http.Request) {
		botAuthHeaderCh <- r.Header.Get("Authorization")
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer closeWebSocketConn(t, conn, "upstream alias bot")

		payload, _ := json.Marshal(map[string]interface{}{
			"type":        "bot_update",
			"instance_id": "bot-123",
		})
		_ = conn.WriteMessage(websocket.TextMessage, payload)
		time.Sleep(100 * time.Millisecond)
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginDelegatedBacktestTestCredentials(t, backendServer.URL, "smoke-user", "Pass123!")

	backtestWSURL := "ws" + backendServer.URL[len("http"):] + "/ws/backtests/alias-run?access_token=" + token
	backtestConn, resp, err := websocket.DefaultDialer.Dial(backtestWSURL, nil)
	defer closeHTTPResponseBody(t, resp, "alias backtest websocket dial")
	if err != nil {
		t.Fatalf("dial alias backtest websocket: %v", err)
	}
	defer closeWebSocketConn(t, backtestConn, "alias backtest")

	_, backtestMsg, err := backtestConn.ReadMessage()
	if err != nil {
		t.Fatalf("read alias backtest message: %v", err)
	}
	var backtestPayload map[string]interface{}
	if err := json.Unmarshal(backtestMsg, &backtestPayload); err != nil {
		t.Fatalf("decode alias backtest payload: %v", err)
	}
	if backtestPayload["run_id"] != "alias-run" {
		t.Fatalf("unexpected alias backtest payload: %v", backtestPayload)
	}

	botWSURL := "ws" + backendServer.URL[len("http"):] + "/ws/bots/bot-123?access_token=" + token
	botConn, resp, err := websocket.DefaultDialer.Dial(botWSURL, nil)
	defer closeHTTPResponseBody(t, resp, "alias bot websocket dial")
	if err != nil {
		t.Fatalf("dial alias bot websocket: %v", err)
	}
	defer closeWebSocketConn(t, botConn, "alias bot")

	_, botMsg, err := botConn.ReadMessage()
	if err != nil {
		t.Fatalf("read alias bot message: %v", err)
	}
	var botPayload map[string]interface{}
	if err := json.Unmarshal(botMsg, &botPayload); err != nil {
		t.Fatalf("decode alias bot payload: %v", err)
	}
	if botPayload["instance_id"] != "bot-123" {
		t.Fatalf("unexpected alias bot payload: %v", botPayload)
	}

	select {
	case authHeader := <-backtestAuthHeaderCh:
		if authHeader == "" {
			t.Fatal("missing upstream alias backtest Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for alias backtest upstream auth header")
	}

	select {
	case authHeader := <-botAuthHeaderCh:
		if authHeader == "" {
			t.Fatal("missing upstream alias bot Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for alias bot upstream auth header")
	}
}
