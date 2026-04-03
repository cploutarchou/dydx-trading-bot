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
			assertFieldTypes(t, got, tc.keys)
		})
	}
}
