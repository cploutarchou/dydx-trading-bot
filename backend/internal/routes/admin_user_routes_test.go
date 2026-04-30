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

func setupAdminUserRouter(t *testing.T) (*gin.Engine, *sql.DB) {
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

	router := gin.New()
	RegisterAdminUserRoutes(router, dbConn)
	return router, dbConn
}

func seedAdminUser(t *testing.T, dbConn *sql.DB, username, email, role string, isActive bool) int {
	t.Helper()
	hashed, err := hashPasswordForTest("Pass123!")
	if err != nil {
		t.Fatalf("hash password: %v", err)
	}

	now := time.Now().UTC()
	result, err := dbConn.Exec(
		`INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		username,
		email,
		role,
		username,
		"",
		hashed,
		isActive,
		role == "admin",
		now,
		now,
	)
	if err != nil {
		t.Fatalf("seed user: %v", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		t.Fatalf("last insert id: %v", err)
	}

	return int(id)
}

func hashPasswordForTest(password string) (string, error) {
	hashed, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return "", err
	}
	return string(hashed), nil
}

func issueAdminBearerToken(t *testing.T, userID int, username, role string) string {
	t.Helper()
	token, err := services.GenerateAccessTokenWithRole(userID, username, role == "admin", role)
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return "Bearer " + token
}

func createUserMFACredentialsSchema(t *testing.T, dbConn *sql.DB) {
	t.Helper()
	if _, err := dbConn.Exec(`
	CREATE TABLE user_mfa_credentials (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL UNIQUE,
		encrypted_secret TEXT NOT NULL,
		encrypted_backup_codes TEXT NOT NULL,
		enabled BOOLEAN NOT NULL DEFAULT 0,
		verified_at DATETIME,
		last_used_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	);`); err != nil {
		t.Fatalf("create user_mfa_credentials table: %v", err)
	}
}

func TestAdminUserRoutes_ListUsers(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	seedAdminUser(t, dbConn, "client1", "client1@example.local", "client", true)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/admin/users", nil)
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			Users []UserResponse `json:"users"`
			Roles []string       `json:"roles"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(body.Data.Users) != 2 {
		t.Fatalf("expected 2 users, got %d", len(body.Data.Users))
	}
	if len(body.Data.Roles) == 0 {
		t.Fatalf("expected roles list")
	}
}

func TestAdminUserRoutes_CreateUser(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)

	payload, _ := json.Marshal(map[string]any{
		"username":  "ops1",
		"email":     "ops1@example.local",
		"password":  "Pass123!",
		"full_name": "Ops User",
		"role":      "marketing",
		"is_active": true,
	})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/admin/users", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", res.Code, res.Body.String())
	}

	var count int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM users WHERE username = ? AND role = ?`, "ops1", "marketing").Scan(&count); err != nil {
		t.Fatalf("count created user: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected created user row")
	}
}

func TestAdminUserRoutes_PreventLastAdminRemoval(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)

	payload, _ := json.Marshal(map[string]any{
		"role": "client",
	})
	req := httptest.NewRequest(http.MethodPut, fmt.Sprintf("/api/v1/admin/users/%d", adminID), bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestAdminUserRoutes_SeedDummyClientsRouteDisabled(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/admin/users/seed-dummy-clients", nil)
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusNotFound {
		t.Fatalf("expected disabled dummy seed route to return 404, got %d body=%s", res.Code, res.Body.String())
	}
}

func TestAdminUserRoutes_ResetUserMFA(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createUserMFACredentialsSchema(t, dbConn)

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	targetID := seedAdminUser(t, dbConn, "ops1", "ops1@example.local", "backoffice", true)

	now := time.Now().UTC()
	if _, err := dbConn.Exec(`UPDATE users SET mfa_enabled = 1 WHERE id = ?`, targetID); err != nil {
		t.Fatalf("enable mfa flag: %v", err)
	}
	if _, err := dbConn.Exec(
		`INSERT INTO user_mfa_credentials (user_id, encrypted_secret, encrypted_backup_codes, enabled, verified_at, last_used_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		targetID,
		"enc-secret",
		"enc-backups",
		true,
		now,
		now,
		now,
		now,
	); err != nil {
		t.Fatalf("insert user mfa credential: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/api/v1/admin/users/%d/reset-mfa", targetID), nil)
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data resetUserMFAResponse `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !body.Data.HadMFAEnabled {
		t.Fatalf("expected prior MFA to be reported as enabled")
	}
	if !body.Data.CredentialRemoved {
		t.Fatalf("expected stored credential to be removed")
	}
	if body.Data.User.MFAEnabled {
		t.Fatalf("expected user mfa_enabled to be false after reset")
	}

	var remainingCredentials int
	if err := dbConn.QueryRow(`SELECT COUNT(*) FROM user_mfa_credentials WHERE user_id = ?`, targetID).Scan(&remainingCredentials); err != nil {
		t.Fatalf("count remaining credentials: %v", err)
	}
	if remainingCredentials != 0 {
		t.Fatalf("expected 0 remaining credentials, got %d", remainingCredentials)
	}

	var mfaEnabled bool
	if err := dbConn.QueryRow(`SELECT mfa_enabled FROM users WHERE id = ?`, targetID).Scan(&mfaEnabled); err != nil {
		t.Fatalf("reload user mfa flag: %v", err)
	}
	if mfaEnabled {
		t.Fatalf("expected mfa flag to be cleared")
	}
}

func TestAdminUserRoutes_ResetUserMFA_IdempotentWhenAlreadyClear(t *testing.T) {
	router, dbConn := setupAdminUserRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	createUserMFACredentialsSchema(t, dbConn)

	adminID := seedAdminUser(t, dbConn, "admin", "admin@example.local", "admin", true)
	targetID := seedAdminUser(t, dbConn, "ops2", "ops2@example.local", "backoffice", true)

	req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/api/v1/admin/users/%d/reset-mfa", targetID), nil)
	req.Header.Set("Authorization", issueAdminBearerToken(t, adminID, "admin", "admin"))
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data resetUserMFAResponse `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Data.HadMFAEnabled {
		t.Fatalf("expected prior MFA to be reported as disabled")
	}
	if body.Data.CredentialRemoved {
		t.Fatalf("expected no credential to be removed")
	}
	if body.Data.User.MFAEnabled {
		t.Fatalf("expected user mfa_enabled to remain false")
	}
}
