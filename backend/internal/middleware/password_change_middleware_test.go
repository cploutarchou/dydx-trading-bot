package middleware

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func runPasswordChangeGate(path string, lookup func(int) (bool, error)) (*gin.Context, *httptest.ResponseRecorder, bool) {
	gin.SetMode(gin.TestMode)
	old := passwordChangeLookup
	passwordChangeLookup = lookup
	defer func() { passwordChangeLookup = old }()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(http.MethodGet, path, nil)
	c.Set("user_id", 7)
	passed := enforcePasswordChangeCleared(c)
	return c, w, passed
}

func TestPasswordChangeGate_AllowsWhenNotRequired(t *testing.T) {
	_, _, passed := runPasswordChangeGate("/api/v1/bots", func(int) (bool, error) {
		return false, nil
	})
	if !passed {
		t.Fatal("request must pass when password_change_required is false")
	}
}

func TestPasswordChangeGate_BlocksWhenRequired(t *testing.T) {
	_, w, passed := runPasswordChangeGate("/api/v1/bots", func(int) (bool, error) {
		return true, nil
	})
	if passed {
		t.Fatal("request must be blocked when password_change_required is true")
	}
	if w.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d body=%s", w.Code, w.Body.String())
	}
	if !contains(w.Body.String(), "password_change_required") {
		t.Fatalf("expected error_code password_change_required, got %s", w.Body.String())
	}
}

func TestPasswordChangeGate_AllowlistsRotationFlows(t *testing.T) {
	allow := []string{
		"/api/v1/auth/change-password",
		"/api/v1/auth/logout",
		"/api/v1/auth/session",
		"/api/v1/auth/2fa/verify",
		"/api/v1/auth/mfa/status",
		// Profile reads the change-password screen needs (the real endpoints;
		// /api/v1/auth/me does not exist as a route).
		"/api/v1/me",
		"/api/v1/users/me",
	}
	for _, path := range allow {
		_, _, passed := runPasswordChangeGate(path, func(int) (bool, error) {
			return true, nil
		})
		if !passed {
			t.Fatalf("allowlisted path %s must pass", path)
		}
	}
}

func TestPasswordChangeGate_FailsClosedOnLookupError(t *testing.T) {
	_, w, passed := runPasswordChangeGate("/api/v1/bots", func(int) (bool, error) {
		return false, errors.New("db down")
	})
	if passed {
		t.Fatal("gate must fail closed when the flag cannot be read")
	}
	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d", w.Code)
	}
}

func TestPasswordChangeGate_InertWithoutLookup(t *testing.T) {
	_, _, passed := runPasswordChangeGate("/api/v1/bots", nil)
	if !passed {
		t.Fatal("gate must be inert when no lookup is installed (tests/tools)")
	}
}
