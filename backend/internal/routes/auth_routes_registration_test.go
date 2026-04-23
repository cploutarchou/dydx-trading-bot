//go:build integration

package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func setupRegistrationRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("JWT_SECRET_KEY", refreshTestJWTSecret)
	t.Setenv("APP_ENV", "test")
	if err := config.LoadConfig(); err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
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

	if _, err := dbConn.Exec(`
	CREATE TABLE invitation_tokens (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		token_code TEXT NOT NULL UNIQUE,
		label TEXT NOT NULL DEFAULT '',
		ib_name TEXT NOT NULL DEFAULT '',
		campaign_name TEXT NOT NULL DEFAULT '',
		max_uses INTEGER NOT NULL DEFAULT 1,
		used_count INTEGER NOT NULL DEFAULT 0,
		created_by_user_id INTEGER,
		last_used_by_user_id INTEGER,
		expires_at DATETIME,
		last_used_at DATETIME,
		revoked_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create invitation_tokens table: %v", err)
	}

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	return router, dbConn
}

func insertBotSetting(t *testing.T, dbConn *sql.DB, key string, value string, valueType string) {
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
		t.Fatalf("insert bot setting %s: %v", key, err)
	}
}

func insertInvitationToken(t *testing.T, dbConn *sql.DB, tokenCode string, maxUses int) {
	t.Helper()
	if _, err := dbConn.Exec(
		`INSERT INTO invitation_tokens (token_code, label, ib_name, campaign_name, max_uses, used_count, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		tokenCode,
		"IB seed token",
		"Default IB",
		"default",
		maxUses,
		0,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert invitation token %s: %v", tokenCode, err)
	}
}

func TestRegistrationStatus_DefaultsEnabled(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/registration-status", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			Enabled            bool   `json:"enabled"`
			Mode               string `json:"mode"`
			InvitationRequired bool   `json:"invitation_required"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !body.Data.Enabled {
		t.Fatalf("expected public registration enabled by default")
	}
	if body.Data.Mode != "open" {
		t.Fatalf("expected registration mode open by default, got %q", body.Data.Mode)
	}
	if body.Data.InvitationRequired {
		t.Fatalf("expected invitation_required false by default")
	}
}

func TestRegister_ForbiddenWhenPublicRegistrationDisabled(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	insertBotSetting(t, dbConn, "allow_public_registration", "false", "boolean")

	payload, _ := json.Marshal(map[string]string{
		"username": "newuser",
		"email":    "newuser@example.local",
		"password": "Pass123!",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/auth/register", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestRegistrationStatus_InvitationMode(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	insertBotSetting(t, dbConn, "registration_mode", "invitation_only", "string")
	insertBotSetting(t, dbConn, "registration_invitation_code", "INVITE-2026", "string")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/registration-status", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			Enabled            bool   `json:"enabled"`
			Mode               string `json:"mode"`
			InvitationRequired bool   `json:"invitation_required"`
			Reason             string `json:"reason"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}

	if !body.Data.Enabled {
		t.Fatalf("expected invitation mode to be enabled when code is configured")
	}
	if body.Data.Mode != "invitation_only" {
		t.Fatalf("expected mode invitation_only, got %q", body.Data.Mode)
	}
	if !body.Data.InvitationRequired {
		t.Fatalf("expected invitation_required true")
	}
	if !strings.Contains(strings.ToLower(body.Data.Reason), "invitation") {
		t.Fatalf("expected invitation-related reason, got %q", body.Data.Reason)
	}
}

func TestRegister_ForbiddenWhenInvitationMissing(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	insertBotSetting(t, dbConn, "registration_mode", "invitation_only", "string")
	insertBotSetting(t, dbConn, "registration_invitation_code", "INVITE-2026", "string")

	payload, _ := json.Marshal(map[string]string{
		"username": "newuser",
		"email":    "newuser@example.local",
		"password": "Pass123!",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/auth/register", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestRegister_SucceedsWithValidInvitationCode(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	insertBotSetting(t, dbConn, "registration_mode", "invitation_only", "string")
	insertBotSetting(t, dbConn, "registration_invitation_code", "INVITE-2026", "string")

	payload, _ := json.Marshal(map[string]string{
		"username":        "inviteuser",
		"email":           "inviteuser@example.local",
		"password":        "Pass123!",
		"invitation_code": "INVITE-2026",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/auth/register", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestRegister_SucceedsWithOneTimeInvitationToken(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	insertBotSetting(t, dbConn, "registration_mode", "invitation_only", "string")
	insertInvitationToken(t, dbConn, "IB-ONETIME-AAAA-BBBB", 1)

	payload, _ := json.Marshal(map[string]string{
		"username":        "tokenuser",
		"email":           "tokenuser@example.local",
		"password":        "Pass123!",
		"invitation_code": "IB-ONETIME-AAAA-BBBB",
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/auth/register", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestRegister_RejectsReusedOneTimeInvitationToken(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	insertBotSetting(t, dbConn, "registration_mode", "invitation_only", "string")
	insertInvitationToken(t, dbConn, "IB-REUSE-AAAA-BBBB", 1)

	firstPayload, _ := json.Marshal(map[string]string{
		"username":        "tokenuser1",
		"email":           "tokenuser1@example.local",
		"password":        "Pass123!",
		"invitation_code": "IB-REUSE-AAAA-BBBB",
	})
	firstReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/register", bytes.NewReader(firstPayload))
	firstReq.Header.Set("Content-Type", "application/json")
	firstRes := httptest.NewRecorder()
	router.ServeHTTP(firstRes, firstReq)
	if firstRes.Code != http.StatusCreated {
		t.Fatalf("expected first registration 201, got %d body=%s", firstRes.Code, firstRes.Body.String())
	}

	secondPayload, _ := json.Marshal(map[string]string{
		"username":        "tokenuser2",
		"email":           "tokenuser2@example.local",
		"password":        "Pass123!",
		"invitation_code": "IB-REUSE-AAAA-BBBB",
	})
	secondReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/register", bytes.NewReader(secondPayload))
	secondReq.Header.Set("Content-Type", "application/json")
	secondRes := httptest.NewRecorder()
	router.ServeHTTP(secondRes, secondReq)

	if secondRes.Code != http.StatusForbidden {
		t.Fatalf("expected second registration 403, got %d body=%s", secondRes.Code, secondRes.Body.String())
	}
}
