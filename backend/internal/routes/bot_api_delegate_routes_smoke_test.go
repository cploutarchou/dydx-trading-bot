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
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	_ "modernc.org/sqlite"
	"golang.org/x/crypto/bcrypt"
)

func TestSmoke_LoginAndDelegatedBacktestLiveWS(t *testing.T) {
	gin.SetMode(gin.TestMode)

	const secret = "smoke-test-jwt-secret-32-characters-min"
	t.Setenv("JWT_SECRET_KEY", secret)
	t.Setenv("APP_ENV", "test")

	upstreamAuthHeaderCh := make(chan string, 1)
	upstreamPayload := map[string]interface{}{
		"type":      "backtest_progress",
		"run_id":    "smoke-run",
		"progress":  42,
		"status":    "running",
		"message":   "delegated-live-update",
		"details":   map[string]interface{}{"source": "upstream"},
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}

	upgrader := websocket.Upgrader{CheckOrigin: func(_ *http.Request) bool { return true }}
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/api/v1/backtests/smoke-run/live", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()

		payload, _ := json.Marshal(upstreamPayload)
		_ = conn.WriteMessage(websocket.TextMessage, payload)
		time.Sleep(100 * time.Millisecond)
	})
	upstreamServer := httptest.NewServer(upstreamMux)
	defer upstreamServer.Close()

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	defer dbConn.Close()

	createUsersTable := `
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
	);`
	if _, err := dbConn.Exec(createUsersTable); err != nil {
		t.Fatalf("create users table: %v", err)
	}

	hash, err := bcrypt.GenerateFromPassword([]byte("SmokePass123!"), bcrypt.DefaultCost)
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

	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             secret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	apiClient := services.NewBotAPIClient(upstreamServer.URL, "")
	RegisterBotAPIDelegateRoutes(router, apiClient)

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody := map[string]string{
		"username": "smoke-user",
		"password": "SmokePass123!",
	}
	loginRaw, _ := json.Marshal(loginBody)
	loginResp, err := http.Post(
		fmt.Sprintf("%s/api/v1/auth/login", backendServer.URL),
		"application/json",
		bytes.NewReader(loginRaw),
	)
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer loginResp.Body.Close()

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
		t.Fatal("login response missing access token")
	}

	wsURL := "ws" + strings.TrimPrefix(backendServer.URL, "http") +
		"/api/v1/backtests/smoke-run/live?access_token=" + tokenResp.AccessToken

	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("dial backend websocket proxy: %v", err)
	}
	defer conn.Close()

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	_, msg, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("read delegated websocket message: %v", err)
	}

	var got map[string]interface{}
	if err := json.Unmarshal(msg, &got); err != nil {
		t.Fatalf("decode websocket payload: %v", err)
	}

	if got["run_id"] != "smoke-run" {
		t.Fatalf("unexpected run_id payload: %v", got["run_id"])
	}

	if got["progress"] != float64(42) {
		t.Fatalf("unexpected progress payload: %v", got["progress"])
	}

	select {
	case authHeader := <-upstreamAuthHeaderCh:
		if authHeader == "" {
			t.Fatal("upstream websocket missing Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream auth header")
	}
}

func TestSmoke_LoginAndDelegatedStrategyWS(t *testing.T) {
	gin.SetMode(gin.TestMode)

	const secret = "smoke-test-jwt-secret-32-characters-min"
	t.Setenv("JWT_SECRET_KEY", secret)
	t.Setenv("APP_ENV", "test")

	upstreamAuthHeaderCh := make(chan string, 1)
	strategyPayload := map[string]interface{}{
		"type":       "strategy_status",
		"strategyId": 101,
		"status":     "running",
		"updatedAt":  time.Now().UTC().Format(time.RFC3339),
	}

	upgrader := websocket.Upgrader{CheckOrigin: func(_ *http.Request) bool { return true }}
	upstreamMux := http.NewServeMux()
	upstreamMux.HandleFunc("/ws/strategies", func(w http.ResponseWriter, r *http.Request) {
		upstreamAuthHeaderCh <- r.Header.Get("Authorization")
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()

		payload, _ := json.Marshal(strategyPayload)
		_ = conn.WriteMessage(websocket.TextMessage, payload)
		time.Sleep(100 * time.Millisecond)
	})
	upstreamServer := httptest.NewServer(upstreamMux)
	defer upstreamServer.Close()

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	defer dbConn.Close()

	createUsersTable := `
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
	);`
	if _, err := dbConn.Exec(createUsersTable); err != nil {
		t.Fatalf("create users table: %v", err)
	}

	hash, err := bcrypt.GenerateFromPassword([]byte("SmokePass123!"), bcrypt.DefaultCost)
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

	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             secret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	apiClient := services.NewBotAPIClient(upstreamServer.URL, "")
	RegisterBotAPIDelegateRoutes(router, apiClient)

	backendServer := httptest.NewServer(router)
	defer backendServer.Close()

	loginBody := map[string]string{
		"username": "smoke-user",
		"password": "SmokePass123!",
	}
	loginRaw, _ := json.Marshal(loginBody)
	loginResp, err := http.Post(
		fmt.Sprintf("%s/api/v1/auth/login", backendServer.URL),
		"application/json",
		bytes.NewReader(loginRaw),
	)
	if err != nil {
		t.Fatalf("login request: %v", err)
	}
	defer loginResp.Body.Close()

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
		t.Fatal("login response missing access token")
	}

	wsURL := "ws" + strings.TrimPrefix(backendServer.URL, "http") +
		"/ws/strategies?access_token=" + tokenResp.AccessToken

	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("dial backend strategy websocket proxy: %v", err)
	}
	defer conn.Close()

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	_, msg, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("read delegated strategy websocket message: %v", err)
	}

	var got map[string]interface{}
	if err := json.Unmarshal(msg, &got); err != nil {
		t.Fatalf("decode strategy websocket payload: %v", err)
	}

	if got["type"] != "strategy_status" {
		t.Fatalf("unexpected strategy payload type: %v", got["type"])
	}

	select {
	case authHeader := <-upstreamAuthHeaderCh:
		if authHeader == "" {
			t.Fatal("upstream strategy websocket missing Authorization header")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timeout waiting for upstream strategy auth header")
	}
}
