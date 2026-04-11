//go:build integration

package routes

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupPortalMFATestRouter(t *testing.T, mfaEnabled bool) (*gin.Engine, *sql.DB) {
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
		role TEXT NOT NULL DEFAULT 'client',
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		mfa_enabled BOOLEAN NOT NULL DEFAULT 0,
		password_change_required BOOLEAN NOT NULL DEFAULT 0,
		last_login DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create users table: %v", err)
	}

	if _, err := dbConn.Exec(`
	CREATE TABLE bot_settings (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		section TEXT NOT NULL,
		key TEXT NOT NULL,
		value TEXT NOT NULL,
		value_type TEXT NOT NULL,
		description TEXT NOT NULL DEFAULT '',
		default_value TEXT NOT NULL DEFAULT '',
		is_active BOOLEAN NOT NULL DEFAULT 1,
		version INTEGER NOT NULL DEFAULT 1,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create bot_settings table: %v", err)
	}

	hash, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate hash: %v", err)
	}

	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO users (id, username, email, role, full_name, avatar, hashed_password, is_active, is_admin, mfa_enabled, password_change_required, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		1,
		"ops",
		"ops@example.local",
		"backoffice",
		"Ops User",
		"",
		string(hash),
		true,
		false,
		mfaEnabled,
		false,
		now,
		now,
	); err != nil {
		t.Fatalf("insert user: %v", err)
	}

	router := gin.New()
	RegisterPortalRoutes(router, dbConn)
	return router, dbConn
}

func insertPortalMFATestSetting(t *testing.T, dbConn *sql.DB, key, value, valueType string) {
	t.Helper()
	if _, err := dbConn.Exec(
		`INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"platform",
		key,
		value,
		valueType,
		key,
		value,
		true,
		1,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert setting %s: %v", key, err)
	}
}

func issuePortalMFATestBearerToken(t *testing.T) string {
	t.Helper()
	token, err := services.GenerateAccessTokenWithRole(1, "ops", false, "backoffice")
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return "Bearer " + token
}

func TestPortalRoutes_CRMRequiresMFAForPrivilegedRoles(t *testing.T) {
	router, dbConn := setupPortalMFATestRouter(t, false)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})
	insertPortalMFATestSetting(t, dbConn, "require_privileged_mfa", "true", "boolean")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/admin/crm/summary", nil)
	req.Header.Set("Authorization", issuePortalMFATestBearerToken(t))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d body=%s", res.Code, res.Body.String())
	}

	var body map[string]any
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body["code"] != "mfa_required" {
		t.Fatalf("expected mfa_required code, got %v", body["code"])
	}
	if body["message"] != "MFA enrollment required for this operation" {
		t.Fatalf("unexpected message: %v", body["message"])
	}
}

func TestPortalRoutes_CRMAllowsPrivilegedRoleWhenMFARequirementDisabled(t *testing.T) {
	router, dbConn := setupPortalMFATestRouter(t, false)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})
	insertPortalMFATestSetting(t, dbConn, "require_privileged_mfa", "false", "boolean")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/admin/crm/summary", nil)
	req.Header.Set("Authorization", issuePortalMFATestBearerToken(t))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200 when privileged MFA disabled, got %d body=%s", res.Code, res.Body.String())
	}
	if strings.Contains(strings.ToLower(res.Body.String()), "mfa enrollment required") {
		t.Fatalf("response should not mention mfa requirement when disabled: %s", res.Body.String())
	}
}
