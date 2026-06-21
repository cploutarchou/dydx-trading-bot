//go:build integration

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
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"github.com/pquerna/otp/totp"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupAuthMFATestRouter(t *testing.T) (*gin.Engine, *sql.DB, int) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("JWT_SECRET_KEY", refreshTestJWTSecret)
	t.Setenv("APP_ENV", "test")
	t.Setenv("ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
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
	CREATE TABLE user_mfa_credentials (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL UNIQUE,
		encrypted_secret TEXT NOT NULL,
		encrypted_backup_codes TEXT NOT NULL,
		enabled BOOLEAN NOT NULL DEFAULT 0,
		verified_at DATETIME,
		last_used_at DATETIME,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
	);`); err != nil {
		t.Fatalf("create user_mfa_credentials table: %v", err)
	}

	hash, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("generate hash: %v", err)
	}

	now := time.Now().UTC()
	_, err := dbConn.Exec(
		`INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, mfa_enabled, password_change_required, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"alice",
		"alice@example.local",
		"admin",
		"Alice",
		"",
		string(hash),
		true,
		true,
		false,
		false,
		now,
		now,
	)
	if err != nil {
		t.Fatalf("insert user: %v", err)
	}
	var insertID int
	if err := dbConn.QueryRow(`SELECT id FROM users WHERE username = ?`, "alice").Scan(&insertID); err != nil {
		t.Fatalf("lookup inserted user id: %v", err)
	}

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	return router, dbConn, insertID
}

func issueMFATestBearerToken(t *testing.T, userID int, username, role string) string {
	t.Helper()
	token, err := services.GenerateAccessTokenWithRole(userID, username, role == "admin", role)
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return "Bearer " + token
}

func TestAuth2FA_SetupAndVerifyEnablesMFA(t *testing.T) {
	router, dbConn, userID := setupAuthMFATestRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	setupReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/setup", bytes.NewReader([]byte(`{}`)))
	setupReq.Header.Set("Content-Type", "application/json")
	setupReq.Header.Set("Authorization", issueMFATestBearerToken(t, userID, "alice", "admin"))
	setupRes := httptest.NewRecorder()
	router.ServeHTTP(setupRes, setupReq)

	if setupRes.Code != http.StatusOK {
		t.Fatalf("expected setup 200, got %d body=%s", setupRes.Code, setupRes.Body.String())
	}

	var setupBody struct {
		Success bool   `json:"success"`
		Message string `json:"message"`
		Data    struct {
			Secret      string   `json:"secret"`
			QRCode      string   `json:"qr_code"`
			BackupCodes []string `json:"backup_codes"`
		} `json:"data"`
	}
	if err := json.Unmarshal(setupRes.Body.Bytes(), &setupBody); err != nil {
		t.Fatalf("decode setup response: %v", err)
	}
	if !setupBody.Success {
		t.Fatalf("expected success response: %s", setupRes.Body.String())
	}
	if setupBody.Data.Secret == "" {
		t.Fatalf("expected setup secret")
	}
	if setupBody.Data.QRCode == "" {
		t.Fatalf("expected qr code")
	}
	if len(setupBody.Data.BackupCodes) != 8 {
		t.Fatalf("expected 8 backup codes, got %d", len(setupBody.Data.BackupCodes))
	}

	var encryptedSecret string
	var enabled bool
	if err := dbConn.QueryRow(`SELECT encrypted_secret, enabled FROM user_mfa_credentials WHERE user_id = ?`, userID).Scan(&encryptedSecret, &enabled); err != nil {
		t.Fatalf("query mfa credential: %v", err)
	}
	if encryptedSecret == "" {
		t.Fatalf("expected encrypted secret to be persisted")
	}
	if enabled {
		t.Fatalf("expected setup to persist disabled credential before verification")
	}

	code, err := totp.GenerateCode(setupBody.Data.Secret, time.Now().UTC())
	if err != nil {
		t.Fatalf("generate totp code: %v", err)
	}
	verifyPayload, _ := json.Marshal(map[string]string{"token": code})
	verifyReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/verify", bytes.NewReader(verifyPayload))
	verifyReq.Header.Set("Content-Type", "application/json")
	verifyReq.Header.Set("Authorization", issueMFATestBearerToken(t, userID, "alice", "admin"))
	verifyRes := httptest.NewRecorder()
	router.ServeHTTP(verifyRes, verifyReq)

	if verifyRes.Code != http.StatusOK {
		t.Fatalf("expected verify 200, got %d body=%s", verifyRes.Code, verifyRes.Body.String())
	}

	var userMFAEnabled bool
	if err := dbConn.QueryRow(`SELECT mfa_enabled FROM users WHERE id = ?`, userID).Scan(&userMFAEnabled); err != nil {
		t.Fatalf("query user mfa_enabled: %v", err)
	}
	if !userMFAEnabled {
		t.Fatalf("expected user.mfa_enabled=true after verification")
	}

	var verifiedCredentialEnabled bool
	var verifiedAt sql.NullTime
	if err := dbConn.QueryRow(`SELECT enabled, verified_at FROM user_mfa_credentials WHERE user_id = ?`, userID).Scan(&verifiedCredentialEnabled, &verifiedAt); err != nil {
		t.Fatalf("query verified credential: %v", err)
	}
	if !verifiedCredentialEnabled {
		t.Fatalf("expected credential enabled after verification")
	}
	if !verifiedAt.Valid {
		t.Fatalf("expected verified_at to be set")
	}
}

func TestAuth2FA_VerifyRejectsInvalidToken(t *testing.T) {
	router, dbConn, userID := setupAuthMFATestRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	setupReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/setup", bytes.NewReader([]byte(`{}`)))
	setupReq.Header.Set("Content-Type", "application/json")
	setupReq.Header.Set("Authorization", issueMFATestBearerToken(t, userID, "alice", "admin"))
	setupRes := httptest.NewRecorder()
	router.ServeHTTP(setupRes, setupReq)
	if setupRes.Code != http.StatusOK {
		t.Fatalf("expected setup 200, got %d body=%s", setupRes.Code, setupRes.Body.String())
	}

	verifyPayload, _ := json.Marshal(map[string]string{"token": "000000"})
	verifyReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/2fa/verify", bytes.NewReader(verifyPayload))
	verifyReq.Header.Set("Content-Type", "application/json")
	verifyReq.Header.Set("Authorization", issueMFATestBearerToken(t, userID, "alice", "admin"))
	verifyRes := httptest.NewRecorder()
	router.ServeHTTP(verifyRes, verifyReq)

	if verifyRes.Code != http.StatusUnauthorized {
		t.Fatalf("expected verify 401, got %d body=%s", verifyRes.Code, verifyRes.Body.String())
	}

	var userMFAEnabled bool
	if err := dbConn.QueryRow(`SELECT mfa_enabled FROM users WHERE id = ?`, userID).Scan(&userMFAEnabled); err != nil {
		t.Fatalf("query user mfa_enabled: %v", err)
	}
	if userMFAEnabled {
		t.Fatalf("expected user.mfa_enabled to remain false")
	}
}
