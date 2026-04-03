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
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

const refreshTestJWTSecret = "refresh-flow-test-secret-32-characters"

func setupAuthTestRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("JWT_SECRET_KEY", refreshTestJWTSecret)
	t.Setenv("APP_ENV", "test")
	config.LoadConfig()
	middleware.InitAuthMiddleware(config.ConfigInstance)

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

	hash, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate hash: %v", err)
	}

	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"alice",
		"alice@example.local",
		"Alice",
		"",
		string(hash),
		true,
		false,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert user: %v", err)
	}

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	return router, dbConn
}

func loginForTokens(t *testing.T, router *gin.Engine) TokenResponse {
	t.Helper()
	loginBody, _ := json.Marshal(map[string]string{"username": "alice", "password": "Pass123!"})
	loginReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/login", bytes.NewReader(loginBody))
	loginReq.Header.Set("Content-Type", "application/json")
	loginRes := httptest.NewRecorder()
	router.ServeHTTP(loginRes, loginReq)
	if loginRes.Code != http.StatusOK {
		t.Fatalf("unexpected login status: %d body=%s", loginRes.Code, loginRes.Body.String())
	}

	var tokenResp TokenResponse
	if err := json.Unmarshal(loginRes.Body.Bytes(), &tokenResp); err != nil {
		t.Fatalf("decode login response: %v", err)
	}
	return tokenResp
}

func TestAuthRefresh_ValidRefreshTokenReturnsNewTokens(t *testing.T) {
	router, dbConn := setupAuthTestRouter(t)
	defer dbConn.Close()
	tokens := loginForTokens(t, router)

	refreshBody, _ := json.Marshal(map[string]string{"refresh_token": tokens.RefreshToken})
	refreshReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/refresh", bytes.NewReader(refreshBody))
	refreshReq.Header.Set("Content-Type", "application/json")
	refreshRes := httptest.NewRecorder()
	router.ServeHTTP(refreshRes, refreshReq)

	if refreshRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", refreshRes.Code, refreshRes.Body.String())
	}
}

func TestAuthRefresh_AccessTokenRejectedForRefresh(t *testing.T) {
	router, dbConn := setupAuthTestRouter(t)
	defer dbConn.Close()
	tokens := loginForTokens(t, router)

	refreshBody, _ := json.Marshal(map[string]string{"refresh_token": tokens.AccessToken})
	refreshReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/refresh", bytes.NewReader(refreshBody))
	refreshReq.Header.Set("Content-Type", "application/json")
	refreshRes := httptest.NewRecorder()
	router.ServeHTTP(refreshRes, refreshReq)

	if refreshRes.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d body=%s", refreshRes.Code, refreshRes.Body.String())
	}

	var body map[string]interface{}
	_ = json.Unmarshal(refreshRes.Body.Bytes(), &body)
	if body["error"] != "invalid token type for refresh" {
		t.Fatalf("unexpected error body: %v", body)
	}
}

func TestAuthRefresh_NonPositiveUserIDFallsBackToUserNotFound(t *testing.T) {
	router, dbConn := setupAuthTestRouter(t)
	defer dbConn.Close()

	mgr := auth.NewManager(auth.JWTConfig{
		Secret:            refreshTestJWTSecret,
		ExpiryHours:       1,
		RefreshExpiryDays: 7,
	})
	refreshToken, _, err := mgr.CreateRefreshToken(0, "nobody", "", false)
	if err != nil {
		t.Fatalf("create refresh token: %v", err)
	}

	refreshBody, _ := json.Marshal(map[string]string{"refresh_token": refreshToken})
	refreshReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/refresh", bytes.NewReader(refreshBody))
	refreshReq.Header.Set("Content-Type", "application/json")
	refreshRes := httptest.NewRecorder()
	router.ServeHTTP(refreshRes, refreshReq)

	if refreshRes.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d body=%s", refreshRes.Code, refreshRes.Body.String())
	}

	var body map[string]interface{}
	_ = json.Unmarshal(refreshRes.Body.Bytes(), &body)
	if body["error"] != "user not found or inactive" {
		t.Fatalf("unexpected error body: %v", body)
	}
}

func TestAuthRefresh_MalformedTokenDoesNotUseLegacyPayloadError(t *testing.T) {
	router, dbConn := setupAuthTestRouter(t)
	defer dbConn.Close()

	refreshBody, _ := json.Marshal(map[string]string{"refresh_token": "not.a.valid.jwt"})
	refreshReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/refresh", bytes.NewReader(refreshBody))
	refreshReq.Header.Set("Content-Type", "application/json")
	refreshRes := httptest.NewRecorder()
	router.ServeHTTP(refreshRes, refreshReq)

	if refreshRes.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d body=%s", refreshRes.Code, refreshRes.Body.String())
	}

	var body map[string]interface{}
	_ = json.Unmarshal(refreshRes.Body.Bytes(), &body)
	if body["error"] != "invalid or expired refresh token" {
		t.Fatalf("unexpected error body: %v", body)
	}
	if body["error"] == "invalid refresh token payload" {
		t.Fatalf("legacy payload error should not be returned: %v", body)
	}
}

