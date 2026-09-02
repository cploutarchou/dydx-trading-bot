package middleware

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/gin-gonic/gin"
)

func stepUpInit(t *testing.T) {
	t.Helper()
	t.Setenv("JWT_SECRET_KEY", "step-up-test-secret-32-characters!!")
	t.Setenv("SECRET_KEY", "step-up-test-secret-32-characters!!")
	t.Setenv("APP_ENV", "development")
	InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{AccessTokenExpireMinutes: 30, RefreshTokenExpireDays: 7},
	})
}

func stepUpRequest(t *testing.T, sessionToken string) *httptest.ResponseRecorder {
	t.Helper()
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(func(c *gin.Context) {
		c.Set("user_id", 42)
		c.Next()
	})
	r.GET("/protected", RequireRecentMFA(15*time.Minute), func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	if sessionToken != "" {
		req.AddCookie(&http.Cookie{Name: auth.SessionCookieName, Value: sessionToken})
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func issueStepUpSession(t *testing.T, verifiedAt *time.Time) string {
	t.Helper()
	store := AuthSessionStore()
	if store == nil {
		t.Fatal("session store not initialized")
	}
	token, _, err := store.Create(context.Background(), auth.SessionData{
		UserID: 42, Username: "alice", MFARequired: true, MFAVerifiedAt: verifiedAt,
	}, 30*time.Minute)
	if err != nil {
		t.Fatalf("create session: %v", err)
	}
	return token
}

func responseCode(w *httptest.ResponseRecorder) string {
	var body struct {
		Code string `json:"code"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	return body.Code
}

// RequireRecentMFA is the true step-up behind /keys/:network/secret: a session
// with fresh TOTP verification passes; stale, never-verified, missing, or
// bearer-only requests are refused with mfa_step_up_required.
func TestRequireRecentMFA_WindowEnforced(t *testing.T) {
	stepUpInit(t)

	fresh := time.Now().UTC().Add(-2 * time.Minute)
	if w := stepUpRequest(t, issueStepUpSession(t, &fresh)); w.Code != http.StatusOK {
		t.Fatalf("fresh verification must pass, got %d body=%s", w.Code, w.Body.String())
	}

	stale := time.Now().UTC().Add(-30 * time.Minute)
	if w := stepUpRequest(t, issueStepUpSession(t, &stale)); w.Code != http.StatusForbidden || responseCode(w) != "mfa_step_up_required" {
		t.Fatalf("stale verification must 403 with mfa_step_up_required, got %d body=%s", w.Code, w.Body.String())
	}

	if w := stepUpRequest(t, issueStepUpSession(t, nil)); w.Code != http.StatusForbidden || responseCode(w) != "mfa_step_up_required" {
		t.Fatalf("never-verified session must 403 with mfa_step_up_required, got %d body=%s", w.Code, w.Body.String())
	}

	if w := stepUpRequest(t, ""); w.Code != http.StatusForbidden || responseCode(w) != "mfa_step_up_required" {
		t.Fatalf("request without a session (bearer-only) must 403, got %d body=%s", w.Code, w.Body.String())
	}

	if w := stepUpRequest(t, "not-a-real-session-token"); w.Code != http.StatusForbidden || responseCode(w) != "mfa_step_up_required" {
		t.Fatalf("unknown session token must 403, got %d body=%s", w.Code, w.Body.String())
	}
}
