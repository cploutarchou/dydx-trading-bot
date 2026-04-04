package routes

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

type fieldExpectation struct {
	key      string
	typeName string
}

func assertFieldTypes(t *testing.T, body map[string]interface{}, fields []fieldExpectation) {
	t.Helper()
	for _, field := range fields {
		value, exists := body[field.key]
		if !exists {
			t.Fatalf("missing key %q in response: %v", field.key, body)
		}
		switch field.typeName {
		case "string":
			if _, ok := value.(string); !ok {
				t.Fatalf("expected key %q to be string, got %T (%v)", field.key, value, value)
			}
		case "number":
			if _, ok := value.(float64); !ok {
				t.Fatalf("expected key %q to be number, got %T (%v)", field.key, value, value)
			}
		case "array":
			if _, ok := value.([]interface{}); !ok {
				t.Fatalf("expected key %q to be array, got %T (%v)", field.key, value, value)
			}
		default:
			t.Fatalf("unsupported expected type %q", field.typeName)
		}
	}
}

func assertSuccessEnvelope(t *testing.T, payload map[string]interface{}) map[string]interface{} {
	t.Helper()
	if _, ok := payload["success"].(bool); !ok {
		t.Fatalf("expected success bool, got %T (%v)", payload["success"], payload["success"])
	}
	if _, ok := payload["message"].(string); !ok {
		t.Fatalf("expected message string, got %T (%v)", payload["message"], payload["message"])
	}
	if _, ok := payload["timestamp"].(string); !ok {
		t.Fatalf("expected timestamp string, got %T (%v)", payload["timestamp"], payload["timestamp"])
	}
	data, ok := payload["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected data object, got %T (%v)", payload["data"], payload["data"])
	}
	return data
}

func TestContractLock_AuthAndDelegatedHighTrafficEndpoints(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"lock-run","status":"queued"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"backtests":[{"run_id":"lock-run","status":"queued"}],"total":1}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-run/status", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"lock-run","status":"running","progress":34}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouter(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody, _ := json.Marshal(map[string]string{
		"username": "smoke-user",
		"password": "Pass123!",
	})
	loginResp, err := http.Post(backendServer.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(loginBody))
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = loginResp.Body.Close() }()
	if loginResp.StatusCode != http.StatusOK {
		t.Fatalf("expected login 200, got %d", loginResp.StatusCode)
	}

	var loginJSON map[string]interface{}
	if err := json.NewDecoder(loginResp.Body).Decode(&loginJSON); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	assertFieldTypes(t, loginJSON, []fieldExpectation{
		{key: "access_token", typeName: "string"},
		{key: "refresh_token", typeName: "string"},
		{key: "token_type", typeName: "string"},
		{key: "expires_in", typeName: "number"},
	})

	token, _ := loginJSON["access_token"].(string)
	if token == "" {
		t.Fatal("missing access token")
	}

	type endpointCase struct {
		name   string
		method string
		path   string
		body   map[string]interface{}
		keys   []fieldExpectation
	}

	cases := []endpointCase{
		{
			name:   "backtests_run",
			method: http.MethodPost,
			path:   "/api/v1/backtests/run",
			body:   map[string]interface{}{"strategy": "pairs"},
			keys: []fieldExpectation{
				{key: "run_id", typeName: "string"},
				{key: "status", typeName: "string"},
			},
		},
		{
			name:   "backtests_list",
			method: http.MethodGet,
			path:   "/api/v1/backtests",
			keys: []fieldExpectation{
				{key: "backtests", typeName: "array"},
				{key: "total", typeName: "number"},
			},
		},
		{
			name:   "backtests_status",
			method: http.MethodGet,
			path:   "/api/v1/backtests/lock-run/status",
			keys: []fieldExpectation{
				{key: "run_id", typeName: "string"},
				{key: "status", typeName: "string"},
				{key: "progress", typeName: "number"},
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			var bodyReader *bytes.Reader
			if tc.body != nil {
				raw, _ := json.Marshal(tc.body)
				bodyReader = bytes.NewReader(raw)
			} else {
				bodyReader = bytes.NewReader(nil)
			}

			req, err := http.NewRequest(tc.method, backendServer.URL+tc.path, bodyReader)
			if err != nil {
				t.Fatalf("new request: %v", err)
			}
			req.Header.Set("Authorization", "Bearer "+token)
			req.Header.Set("Content-Type", "application/json")

			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				t.Fatalf("request %s failed: %v", tc.path, err)
			}
			defer func() { _ = resp.Body.Close() }()

			if resp.StatusCode != http.StatusOK {
				t.Fatalf("expected 200 for %s, got %d", tc.path, resp.StatusCode)
			}

			var got map[string]interface{}
			if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
				t.Fatalf("decode response %s: %v", tc.path, err)
			}
			data := assertSuccessEnvelope(t, got)
			assertFieldTypes(t, got, tc.keys)
			assertFieldTypes(t, data, tc.keys)
		})
	}
}

func TestContractLock_BacktestSyncHealthEndpoint(t *testing.T) {
	upstreamMux := http.NewServeMux()
	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody, _ := json.Marshal(map[string]string{
		"username": "smoke-user",
		"password": "Pass123!",
	})
	loginResp, err := http.Post(backendServer.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(loginBody))
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = loginResp.Body.Close() }()
	if loginResp.StatusCode != http.StatusOK {
		t.Fatalf("expected login 200, got %d", loginResp.StatusCode)
	}

	var loginJSON map[string]interface{}
	if err := json.NewDecoder(loginResp.Body).Decode(&loginJSON); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	token, _ := loginJSON["access_token"].(string)
	if token == "" {
		t.Fatal("missing access token")
	}

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/sync-health", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode sync-health response: %v", err)
	}

	data := assertSuccessEnvelope(t, got)
	if _, ok := data["runs"].([]interface{}); !ok {
		t.Fatalf("expected data.runs array, got %T (%v)", data["runs"], data["runs"])
	}
	if _, ok := data["count"].(float64); !ok {
		t.Fatalf("expected data.count number, got %T (%v)", data["count"], data["count"])
	}
}

func TestContractLock_BacktestResyncEndpointResponseShape(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/lock-run", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"run_id":"lock-run","status":"completed","start_date":"2025-07-01","end_date":"2025-07-31","num_pairs":3,"total_markets":8}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-run/trades", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"trades":[{"trade_id":"lock-trade","market_1":"BTC-USD","market_2":"ETH-USD","entry_timestamp":"2025-07-10T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.1,"side_1":"BUY","side_2":"SELL","size_1":1,"size_2":2,"hedge_ratio":0.5}]}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-run/position-snapshots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"position_snapshots":[{"position_id":"lock-pos","market_1":"BTC-USD","market_2":"ETH-USD","status":"OPEN","entry_timestamp":"2025-07-10T00:00:00Z","entry_price_1":100,"entry_price_2":200,"entry_z_score":1.1,"size_1":1,"size_2":2,"side_1":"BUY","side_2":"SELL","hedge_ratio":0.5}]}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-run/performance-metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"candles":[{"market":"BTC-USD","timestamp":"2025-07-10T00:00:00Z","resolution":"1HOUR","open":100,"high":101,"low":99,"close":100.5,"volume":12}]}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody, _ := json.Marshal(map[string]string{
		"username": "smoke-user",
		"password": "Pass123!",
	})
	loginResp, err := http.Post(backendServer.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(loginBody))
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = loginResp.Body.Close() }()

	var loginJSON map[string]interface{}
	if err := json.NewDecoder(loginResp.Body).Decode(&loginJSON); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	token, _ := loginJSON["access_token"].(string)
	if token == "" {
		t.Fatal("missing access token")
	}

	req, err := http.NewRequest(http.MethodPost, backendServer.URL+"/api/v1/backtests/lock-run/resync", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("resync request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode response: %v", err)
	}

	data := assertSuccessEnvelope(t, got)

	for _, key := range []string{"run_synced", "trades_synced", "positions_synced", "candles_synced"} {
		if _, ok := data[key].(bool); !ok {
			t.Fatalf("expected data.%s bool, got %T (%v)", key, data[key], data[key])
		}
	}
	assertFieldTypes(t, data, []fieldExpectation{
		{key: "run_id", typeName: "string"},
		{key: "status", typeName: "string"},
		{key: "progress_percent", typeName: "number"},
		{key: "progress_pct", typeName: "number"},
		{key: "progress", typeName: "number"},
		{key: "sync_state", typeName: "string"},
	})
	if _, ok := data["current_task"]; !ok {
		t.Fatalf("expected data.current_task key, got %v", data)
	}
	if _, ok := data["current_pair"]; !ok {
		t.Fatalf("expected data.current_pair key, got %v", data)
	}
}

func TestContractLock_BacktestDetailsStableKeys(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/lock-details", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"run_id":"lock-details","status":"running","progress_percent":42,"total_pnl":12.5,"max_drawdown":7.25},"timestamp":"2026-04-04T00:00:00Z"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody, _ := json.Marshal(map[string]string{"username": "smoke-user", "password": "Pass123!"})
	loginResp, err := http.Post(backendServer.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(loginBody))
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = loginResp.Body.Close() }()
	var loginJSON map[string]interface{}
	if err := json.NewDecoder(loginResp.Body).Decode(&loginJSON); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	token, _ := loginJSON["access_token"].(string)

	req, _ := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/backtests/lock-details", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("details request failed: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var got map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatalf("decode details response: %v", err)
	}

	data := assertSuccessEnvelope(t, got)
	assertFieldTypes(t, data, []fieldExpectation{
		{key: "run_id", typeName: "string"},
		{key: "status", typeName: "string"},
		{key: "progress_percent", typeName: "number"},
		{key: "progress_pct", typeName: "number"},
		{key: "progress", typeName: "number"},
		{key: "total_pnl", typeName: "number"},
		{key: "max_drawdown_pct", typeName: "number"},
	})

	for _, key := range []string{"win_rate", "sharpe_ratio", "total_trades"} {
		value, exists := data[key]
		if !exists {
			t.Fatalf("missing key %q in details data: %v", key, data)
		}
		if value != nil {
			t.Fatalf("expected key %q to be explicit null, got %T (%v)", key, value, value)
		}
	}
}

func TestContractLock_BacktestEmptyStateShapes(t *testing.T) {
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/lock-empty/logs", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-empty/analytics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-empty/position-snapshots", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})
	upstreamMux.HandleFunc("/api/v1/backtests/lock-empty/trades/detailed", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error":"not found"}`))
	})

	router, dbConn := setupDelegatedBacktestAuthRouterWithSync(t, upstreamMux)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody, _ := json.Marshal(map[string]string{"username": "smoke-user", "password": "Pass123!"})
	loginResp, err := http.Post(backendServer.URL+"/api/v1/auth/login", "application/json", bytes.NewReader(loginBody))
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer func() { _ = loginResp.Body.Close() }()
	var loginJSON map[string]interface{}
	if err := json.NewDecoder(loginResp.Body).Decode(&loginJSON); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	token, _ := loginJSON["access_token"].(string)

	type endpointCase struct {
		path  string
		field string
	}
	checks := []endpointCase{
		{path: "/api/v1/backtests/lock-empty/logs", field: "logs"},
		{path: "/api/v1/backtests/lock-empty/analytics", field: "daily_pnl"},
		{path: "/api/v1/backtests/lock-empty/position-snapshots", field: "snapshots"},
		{path: "/api/v1/backtests/lock-empty/positions/snapshots", field: "snapshots"},
		{path: "/api/v1/backtests/lock-empty/trades/detailed", field: "trades"},
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
			t.Fatalf("decode %s payload: %v", check.path, err)
		}
		_ = resp.Body.Close()
		data := assertSuccessEnvelope(t, payload)
		if _, ok := data[check.field].([]interface{}); !ok {
			t.Fatalf("expected data.%s array for %s", check.field, check.path)
		}
	}
}
