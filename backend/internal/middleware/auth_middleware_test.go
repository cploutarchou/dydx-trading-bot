package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/gin-gonic/gin"
)

func makeAccessToken(t *testing.T, secret string, expiresIn time.Duration) string {
	t.Helper()

	mgr := auth.NewManager(auth.JWTConfig{
		Secret:            secret,
		ExpiryHours:       1,
		RefreshExpiryDays: 1,
	})

	token, _, err := mgr.CreateAccessToken(7, "alice", "alice@example.com", true, expiresIn)
	if err != nil {
		t.Fatalf("create access token: %v", err)
	}

	return token
}

func authTestRouter(mw gin.HandlerFunc) *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.GET("/protected", mw, func(c *gin.Context) {
		userID, _ := c.Get("user_id")
		c.JSON(http.StatusOK, gin.H{
			"user_id":  userID,
			"username": c.GetString("username"),
			"email":    c.GetString("email"),
			"is_admin": c.GetBool("is_admin"),
		})
	})
	return r
}

func TestRequireAuth_Returns500WhenNotInitialized(t *testing.T) {
	jwtManager = nil
	router := authTestRouter(RequireAuth())

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", w.Code)
	}
}

func TestRequireAuth_AllowsValidBearerAndSetsClaims(t *testing.T) {
	const secret = "auth-mw-test-secret-32-characters"
	InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             secret,
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	token := makeAccessToken(t, secret, time.Minute)
	router := authTestRouter(RequireAuth())

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if body["username"] != "alice" {
		t.Fatalf("expected username alice, got %v", body["username"])
	}
	if body["email"] != "alice@example.com" {
		t.Fatalf("expected email alice@example.com, got %v", body["email"])
	}
	if body["is_admin"] != true {
		t.Fatalf("expected is_admin=true, got %v", body["is_admin"])
	}
}

func TestRequireAuth_RejectsEmptyBearerToken(t *testing.T) {
	const secret = "auth-mw-test-secret-32-characters"
	InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{JWTSecretKey: secret, AccessTokenExpireMinutes: 30, RefreshTokenExpireDays: 7},
	})
	router := authTestRouter(RequireAuth())

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer   ")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}

func TestRequireAuth_ExpiredTokenReturnsTokenExpiredCode(t *testing.T) {
	const secret = "auth-mw-test-secret-32-characters"
	InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{JWTSecretKey: secret, AccessTokenExpireMinutes: 30, RefreshTokenExpireDays: 7},
	})
	token := makeAccessToken(t, secret, -1*time.Minute)
	router := authTestRouter(RequireAuth())

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", w.Code)
	}

	var body map[string]interface{}
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "token_expired" {
		t.Fatalf("expected code token_expired, got %v", body["code"])
	}
}

func TestAuthMiddleware_DelegatesToRequireAuth(t *testing.T) {
	const secret = "auth-mw-test-secret-32-characters"
	InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{JWTSecretKey: secret, AccessTokenExpireMinutes: 30, RefreshTokenExpireDays: 7},
	})
	token := makeAccessToken(t, secret, time.Minute)
	router := authTestRouter(AuthMiddleware())

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}
