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
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

// setupTransportRouter builds a test router whose bot-API client points to
// botAPIBaseURL and uses the provided httpClient (nil → default 30 s client).
func setupTransportRouter(t *testing.T, botAPIBaseURL string, botHTTPClient *http.Client) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	const secret = "transport-test-jwt-secret-32-chars-x"
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

	hash, err := bcrypt.GenerateFromPassword([]byte("TransportPass1!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate password hash: %v", err)
	}
	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"transport-user", "transport-user@example.local", "Transport User", "",
		string(hash), true, false, time.Now().UTC(), time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert transport user: %v", err)
	}

	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             secret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	apiClient := services.NewBotAPIClient(botAPIBaseURL, "")
	if botHTTPClient != nil {
		apiClient = apiClient.WithHTTPClient(botHTTPClient)
	}

	router := gin.New()
	router.Use(middleware.RequestTraceMiddleware())
	RegisterAuthRoutes(router, dbConn)
	RegisterBotAPIDelegateRoutes(router, apiClient)

	return router, dbConn
}

// loginTransportTestUser logs in the transport test user and returns the access token.
func loginTransportTestUser(t *testing.T, backendURL string) string {
	t.Helper()
	loginBody, _ := json.Marshal(map[string]string{
		"username": "transport-user",
		"password": "TransportPass1!",
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

// TestDelegatedRoute_ConnectionRefused_Returns502 verifies that when the upstream
// bot API is not running, delegated routes return HTTP 502 with an informative message.
func TestDelegatedRoute_ConnectionRefused_Returns502(t *testing.T) {
	// Grab a free port by starting a dummy server, note URL, then close it.
	dummyServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	closedURL := dummyServer.URL
	dummyServer.Close() // port now refuses connections

	router, dbConn := setupTransportRouter(t, closedURL, nil)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginTransportTestUser(t, backendServer.URL)

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/system/status", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("execute request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusBadGateway {
		t.Fatalf("expected 502 Bad Gateway, got %d", resp.StatusCode)
	}

	var body map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode response body: %v", err)
	}
	errorMsg, _ := body["error"].(string)
	if errorMsg == "" {
		t.Fatalf("expected non-empty 'error' field in 502 response, got: %v", body)
	}
	message, _ := body["message"].(string)
	if message == "" {
		t.Fatalf("expected non-empty 'message' field in 502 response, got: %v", body)
	}
}

// TestDelegatedRoute_UpstreamTimeout_Returns504 verifies that when the upstream
// bot API stalls indefinitely, delegated routes return HTTP 504 Gateway Timeout.
func TestDelegatedRoute_UpstreamTimeout_Returns504(t *testing.T) {
	// Upstream that accepts the connection but never writes a response.
	hangServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-r.Context().Done() // unblocks when client disconnects / server closes
	}))
	t.Cleanup(hangServer.Close)

	// Use a very short client timeout so the test completes quickly.
	fastClient := &http.Client{Timeout: 75 * time.Millisecond}
	router, dbConn := setupTransportRouter(t, hangServer.URL, fastClient)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginTransportTestUser(t, backendServer.URL)

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/system/status", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	// Use a separate http.Client with a longer timeout so the *test client* doesn't
	// race the bot-client's 75 ms timeout.
	testHTTPClient := &http.Client{Timeout: 5 * time.Second}
	resp, err := testHTTPClient.Do(req)
	if err != nil {
		t.Fatalf("execute request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusGatewayTimeout {
		t.Fatalf("expected 504 Gateway Timeout, got %d", resp.StatusCode)
	}

	var body map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode response body: %v", err)
	}
	errorMsg, _ := body["error"].(string)
	if errorMsg == "" {
		t.Fatalf("expected non-empty 'error' field in 504 response, got: %v", body)
	}
	message, _ := body["message"].(string)
	if message == "" {
		t.Fatalf("expected non-empty 'message' field in 504 response, got: %v", body)
	}
}

// TestDelegatedRoute_UpstreamStatus_StillPassedThrough ensures that real upstream
// 4xx responses still come through correctly after the transport error changes.
func TestDelegatedRoute_UpstreamStatus_StillPassedThrough(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"error":"upstream forbidden"}`))
	}))
	t.Cleanup(upstream.Close)

	router, dbConn := setupTransportRouter(t, upstream.URL, nil)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginTransportTestUser(t, backendServer.URL)

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/system/status", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("execute request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected 403 passthrough, got %d", resp.StatusCode)
	}
	var body map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode response body: %v", err)
	}
	if body["error"] != "upstream forbidden" {
		t.Fatalf("unexpected response body: %v", body)
	}
	if body["message"] != "upstream forbidden" {
		t.Fatalf("unexpected passthrough message: %v", body)
	}
}

func TestDelegatedRoute_ServiceTokenModeSkipsCallerJWT(t *testing.T) {
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "true")
	t.Setenv("BOT_API_TOKEN", "shared-service-token")

	authHeaders := make(chan string, 2)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeaders <- r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		if r.Header.Get("Authorization") != "Bearer shared-service-token" {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"detail":"Invalid token"}`))
			return
		}
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"healthy":true}}`))
	}))
	t.Cleanup(upstream.Close)

	router, dbConn := setupTransportRouter(t, upstream.URL, nil)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginTransportTestUser(t, backendServer.URL)

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/system/status", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("execute request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", resp.StatusCode)
	}

	first := <-authHeaders
	if first != "Bearer shared-service-token" {
		t.Fatalf("expected upstream request to use configured service token directly, got %q", first)
	}
	select {
	case extra := <-authHeaders:
		t.Fatalf("expected a single upstream auth attempt, got extra header %q", extra)
	case <-time.After(150 * time.Millisecond):
	}
}

func TestDelegatedRoute_PropagatesTraceHeader(t *testing.T) {
	upstreamTraceCh := make(chan string, 1)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upstreamTraceCh <- r.Header.Get("X-Trace-Id")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"success":true,"message":"ok","data":{"healthy":true}}`))
	}))
	t.Cleanup(upstream.Close)

	router, dbConn := setupTransportRouter(t, upstream.URL, nil)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginTransportTestUser(t, backendServer.URL)

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/system/status", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-Trace-Id", "req-route-trace")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("execute request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", resp.StatusCode)
	}
	if got := resp.Header.Get("X-Trace-Id"); got != "req-route-trace" {
		t.Fatalf("expected response trace header to echo inbound trace, got %q", got)
	}

	select {
	case got := <-upstreamTraceCh:
		if got != "req-route-trace" {
			t.Fatalf("expected upstream trace header, got %q", got)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream trace header")
	}
}

func TestDelegatedRoute_UpstreamMessageField_StillPassedThrough(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusTooManyRequests)
		_, _ = w.Write([]byte(`{"message":"upstream rate limited"}`))
	}))
	t.Cleanup(upstream.Close)

	router, dbConn := setupTransportRouter(t, upstream.URL, nil)
	defer func() { _ = dbConn.Close() }()
	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	token := loginTransportTestUser(t, backendServer.URL)

	req, err := http.NewRequest(http.MethodGet, backendServer.URL+"/api/v1/system/status", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("execute request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusTooManyRequests {
		t.Fatalf("expected 429 passthrough, got %d", resp.StatusCode)
	}
	var body map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode response body: %v", err)
	}
	if body["error"] != "upstream rate limited" || body["message"] != "upstream rate limited" {
		t.Fatalf("unexpected response body: %v", body)
	}
}
