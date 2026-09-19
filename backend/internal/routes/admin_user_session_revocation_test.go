//go:build integration

package routes

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
)

// openSessionFor mints a session for the user exactly as login does, so the
// tests observe revocation through the same store the auth middleware reads.
func openSessionFor(t *testing.T, userID int, role string) string {
	t.Helper()
	store := middleware.AuthSessionStore()
	if store == nil {
		t.Fatal("session store not initialised")
	}
	token, _, err := store.Create(context.Background(), auth.SessionData{
		UserID:   userID,
		Username: fmt.Sprintf("user-%d", userID),
		Role:     role,
		IsAdmin:  role == "admin",
	}, time.Hour)
	if err != nil {
		t.Fatalf("create session: %v", err)
	}
	return token
}

func assertSessionState(t *testing.T, token string, wantAlive bool) {
	t.Helper()
	data, err := middleware.AuthSessionStore().Get(context.Background(), token)
	alive := err == nil && data != nil
	if alive != wantAlive {
		t.Fatalf("session alive=%v, want %v (err=%v)", alive, wantAlive, err)
	}
	if !wantAlive && !errors.Is(err, auth.ErrSessionNotFound) {
		t.Fatalf("expected ErrSessionNotFound for a revoked session, got %v", err)
	}
}

func adminPut(t *testing.T, router http.Handler, adminID int, path string, body map[string]any) *httptest.ResponseRecorder {
	t.Helper()
	payload, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPut, path, bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	return res
}

func TestAdminUserRoutes_DeactivateRevokesSessions(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	targetID := seedAdminUser(t, dbConn, "leaver", "leaver@example.local", "client", true)
	session := openSessionFor(t, targetID, "client")
	assertSessionState(t, session, true)

	res := adminPut(t, router, adminID, fmt.Sprintf("/api/v1/admin/users/%d/status", targetID), map[string]any{"is_active": false})
	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	assertSessionState(t, session, false)
}

func TestAdminUserRoutes_RoleChangeRevokesSessions(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	demotedID := seedAdminUser(t, dbConn, "second-admin", "second@example.local", "admin", true)
	session := openSessionFor(t, demotedID, "admin")

	res := adminPut(t, router, adminID, fmt.Sprintf("/api/v1/admin/users/%d/role", demotedID), map[string]any{"role": "client"})
	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	// The old session carried is_admin=true; it must not outlive the demotion.
	assertSessionState(t, session, false)
}

func TestAdminUserRoutes_ProfileOnlyUpdateKeepsSessions(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	targetID := seedAdminUser(t, dbConn, "renamed", "renamed@example.local", "client", true)
	session := openSessionFor(t, targetID, "client")

	res := adminPut(t, router, adminID, fmt.Sprintf("/api/v1/admin/users/%d", targetID), map[string]any{"full_name": "New Name"})
	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	assertSessionState(t, session, true)
}

func TestAdminUserRoutes_ResetPasswordRevokesSessions(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() { _ = dbConn.Close() })

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	targetID := seedAdminUser(t, dbConn, "compromised", "compromised@example.local", "client", true)
	session := openSessionFor(t, targetID, "client")

	req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/api/v1/admin/users/%d/reset-password", targetID), bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	assertSessionState(t, session, false)
}
