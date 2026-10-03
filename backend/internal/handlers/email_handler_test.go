package handlers

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func newEmailHandlerRouter(t *testing.T, isAdmin bool, email string) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)
	t.Setenv("ENCRYPTION_KEY", "email-handler-test-encryption-key!")
	t.Setenv("PLUNK_API_URL", "")

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	dbConn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = dbConn.Close() })
	for _, statement := range []string{
		`CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL DEFAULT 'client', full_name TEXT, avatar TEXT, hashed_password TEXT NOT NULL, is_active BOOLEAN NOT NULL DEFAULT 1, is_admin BOOLEAN NOT NULL DEFAULT 0, password_change_required BOOLEAN NOT NULL DEFAULT 0, last_login DATETIME, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL);`,
		`CREATE TABLE bot_settings (id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, value_type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', default_value TEXT NOT NULL DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL);`,
		`CREATE TABLE external_api_credentials (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, provider TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', encrypted_api_key TEXT NOT NULL, api_key_hash TEXT NOT NULL DEFAULT '', api_key_salt TEXT NOT NULL DEFAULT '', api_key_masked TEXT NOT NULL DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, CONSTRAINT uq_external_api_credentials_user_provider UNIQUE (user_id, provider));`,
	} {
		if _, err := dbConn.Exec(statement); err != nil {
			t.Fatalf("setup schema: %v", err)
		}
	}

	handler := NewEmailHandler(services.NewEmailService(
		services.NewExternalAPICredentialService(repository.NewExternalAPICredentialRepository(dbConn)),
		repository.NewSettingsRepository(dbConn),
		repository.NewUserRepository(dbConn),
	))

	router := gin.New()
	router.Use(func(c *gin.Context) {
		c.Set("is_admin", isAdmin)
		c.Set("email", email)
		c.Next()
	})
	router.GET("/email/status", handler.GetStatus)
	router.PUT("/email/config", handler.SaveConfig)
	router.DELETE("/email/config", handler.DeleteConfig)
	router.POST("/email/test", handler.SendTest)
	return router
}

func doEmailRequest(router *gin.Engine, method, path string, body any) *httptest.ResponseRecorder {
	var reader io.Reader
	if body != nil {
		encoded, _ := json.Marshal(body)
		reader = bytes.NewReader(encoded)
	}
	req := httptest.NewRequest(method, path, reader)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	return recorder
}

func TestEmailHandler_RejectsNonAdmins(t *testing.T) {
	router := newEmailHandlerRouter(t, false, "client@example.com")
	for _, tc := range []struct{ method, path string }{
		{http.MethodGet, "/email/status"},
		{http.MethodPut, "/email/config"},
		{http.MethodDelete, "/email/config"},
		{http.MethodPost, "/email/test"},
	} {
		if got := doEmailRequest(router, tc.method, tc.path, map[string]string{}).Code; got != http.StatusForbidden {
			t.Fatalf("%s %s = %d, want 403", tc.method, tc.path, got)
		}
	}
}

func TestEmailHandler_SaveThenTestSendsToTheSignedInAdmin(t *testing.T) {
	var recipient string
	plunk := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload map[string]any
		_ = json.NewDecoder(r.Body).Decode(&payload)
		recipient, _ = payload["to"].(string)
		_, _ = io.WriteString(w, `{"success":true,"emails":[{"email":"msg-7"}]}`)
	}))
	defer plunk.Close()

	router := newEmailHandlerRouter(t, true, "admin@example.com")

	if got := doEmailRequest(router, http.MethodPost, "/email/test", nil); got.Code != http.StatusBadGateway {
		t.Fatalf("test before configuring = %d, want 502: %s", got.Code, got.Body.String())
	}

	saved := doEmailRequest(router, http.MethodPut, "/email/config", map[string]string{
		"api_key": "sk_handler_test_key_0123456789", "api_url": plunk.URL, "from_email": "no-reply@executionlab.io",
	})
	if saved.Code != http.StatusOK {
		t.Fatalf("save = %d: %s", saved.Code, saved.Body.String())
	}
	if bytes.Contains(saved.Body.Bytes(), []byte("sk_handler_test_key_0123456789")) {
		t.Fatal("save response leaks the secret key")
	}

	bad := doEmailRequest(router, http.MethodPut, "/email/config", map[string]string{
		"api_key": "sk_x", "api_url": "http://plain.example.com", "from_email": "no-reply@executionlab.io",
	})
	if bad.Code != http.StatusBadRequest {
		t.Fatalf("plain-http save = %d, want 400", bad.Code)
	}

	tested := doEmailRequest(router, http.MethodPost, "/email/test", nil)
	if tested.Code != http.StatusOK {
		t.Fatalf("test send = %d: %s", tested.Code, tested.Body.String())
	}
	if recipient != "admin@example.com" {
		t.Fatalf("test message went to %q, want the signed-in admin", recipient)
	}

	explicit := doEmailRequest(router, http.MethodPost, "/email/test", map[string]string{"to": "ops@example.com"})
	if explicit.Code != http.StatusOK || recipient != "ops@example.com" {
		t.Fatalf("explicit recipient: code=%d recipient=%q", explicit.Code, recipient)
	}

	if got := doEmailRequest(router, http.MethodDelete, "/email/config", nil); got.Code != http.StatusOK {
		t.Fatalf("delete = %d", got.Code)
	}
	if got := doEmailRequest(router, http.MethodPost, "/email/test", nil); got.Code != http.StatusBadGateway {
		t.Fatalf("test after delete = %d, want 502", got.Code)
	}
}
