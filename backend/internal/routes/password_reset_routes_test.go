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
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

const passwordResetTestJWTSecret = "password-reset-test-secret-key-0123456789"

func setupPasswordResetRouter(t *testing.T) (*gin.Engine, *sql.DB) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("JWT_SECRET_KEY", passwordResetTestJWTSecret)
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
	);
	CREATE TABLE password_reset_tokens (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		token_hash TEXT NOT NULL UNIQUE,
		expires_at DATETIME NOT NULL,
		used_at DATETIME,
		created_at DATETIME NOT NULL,
		created_ip TEXT NOT NULL DEFAULT ''
	);
	`); err != nil {
		t.Fatalf("fixture ddl: %v", err)
	}

	hashed, err := bcrypt.GenerateFromPassword([]byte("OldPassword123"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("hash seed password: %v", err)
	}
	now := time.Now().UTC()
	if _, err := dbConn.Exec(
		`INSERT INTO users (username, email, full_name, avatar, hashed_password, is_active, created_at, updated_at) VALUES (?, ?, ?, '', ?, 1, ?, ?)`,
		"reset_user", "reset@example.test", "Reset User", string(hashed), now, now); err != nil {
		t.Fatalf("seed user: %v", err)
	}

	router := gin.New()
	auth := router.Group("/api/v1/auth")
	{
		auth.POST("/forgot-password", forgotPasswordHandler(dbConn))
		auth.POST("/reset-password", resetPasswordHandler(dbConn))
	}
	return router, dbConn
}

func postJSON(t *testing.T, router *gin.Engine, path string, body map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	raw, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)
	return rec
}

func seedValidResetToken(t *testing.T, db *sql.DB, userID int) string {
	t.Helper()
	raw := "test-reset-token-value-abcdef"
	repo := repository.NewPasswordResetTokenRepository(db)
	if err := repo.Create(t.Context(), userID, services.HashForValidation(raw), time.Now().UTC().Add(30*time.Minute), "127.0.0.1"); err != nil {
		t.Fatalf("seed reset token: %v", err)
	}
	return raw
}

func TestForgotPassword_UnknownEmailGetsGenericResponse(t *testing.T) {
	router, _ := setupPasswordResetRouter(t)
	rec := postJSON(t, router, "/api/v1/auth/forgot-password", map[string]string{"email": "nobody@example.test"})
	if rec.Code != http.StatusOK {
		t.Fatalf("unknown email: status=%d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "reset link") {
		t.Fatalf("unknown email should get the same generic copy, got: %s", rec.Body.String())
	}
}

func TestForgotPassword_InvalidBodyRejected(t *testing.T) {
	router, _ := setupPasswordResetRouter(t)
	rec := postJSON(t, router, "/api/v1/auth/forgot-password", map[string]string{"email": "not-an-email"})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("invalid email: status=%d", rec.Code)
	}
}

func TestResetPassword_FullFlow(t *testing.T) {
	router, db := setupPasswordResetRouter(t)

	var userID int
	if err := db.QueryRow(`SELECT id FROM users WHERE username = 'reset_user'`).Scan(&userID); err != nil {
		t.Fatalf("lookup seed user: %v", err)
	}
	raw := seedValidResetToken(t, db, userID)

	rec := postJSON(t, router, "/api/v1/auth/reset-password", map[string]string{
		"token": raw, "new_password": "NewPassword456",
	})
	if rec.Code != http.StatusOK {
		t.Fatalf("reset: status=%d body=%s", rec.Code, rec.Body.String())
	}

	var stored string
	if err := db.QueryRow(`SELECT hashed_password FROM users WHERE id = ?`, userID).Scan(&stored); err != nil {
		t.Fatalf("reload user: %v", err)
	}
	if bcrypt.CompareHashAndPassword([]byte(stored), []byte("NewPassword456")) != nil {
		t.Fatal("password was not updated to the new value")
	}
	if bcrypt.CompareHashAndPassword([]byte(stored), []byte("OldPassword123")) == nil {
		t.Fatal("old password still validates after reset")
	}
}

func TestResetPassword_TokenSingleUse(t *testing.T) {
	router, db := setupPasswordResetRouter(t)
	var userID int
	if err := db.QueryRow(`SELECT id FROM users WHERE username = 'reset_user'`).Scan(&userID); err != nil {
		t.Fatalf("lookup seed user: %v", err)
	}
	raw := seedValidResetToken(t, db, userID)

	first := postJSON(t, router, "/api/v1/auth/reset-password", map[string]string{
		"token": raw, "new_password": "NewPassword456",
	})
	if first.Code != http.StatusOK {
		t.Fatalf("first use: status=%d", first.Code)
	}
	second := postJSON(t, router, "/api/v1/auth/reset-password", map[string]string{
		"token": raw, "new_password": "AnotherPassword789",
	})
	if second.Code != http.StatusBadRequest {
		t.Fatalf("replay must be rejected, got status=%d", second.Code)
	}
}

func TestResetPassword_GarbageTokenRejected(t *testing.T) {
	router, _ := setupPasswordResetRouter(t)
	rec := postJSON(t, router, "/api/v1/auth/reset-password", map[string]string{
		"token": "garbage", "new_password": "NewPassword456",
	})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("garbage token: status=%d", rec.Code)
	}
}

func TestResetPassword_ShortPasswordRejected(t *testing.T) {
	router, db := setupPasswordResetRouter(t)
	var userID int
	if err := db.QueryRow(`SELECT id FROM users WHERE username = 'reset_user'`).Scan(&userID); err != nil {
		t.Fatalf("lookup seed user: %v", err)
	}
	raw := seedValidResetToken(t, db, userID)

	rec := postJSON(t, router, "/api/v1/auth/reset-password", map[string]string{
		"token": raw, "new_password": "short",
	})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("short password: status=%d", rec.Code)
	}

	// Token must NOT be consumed by a rejected request.
	var used sql.NullTime
	if err := db.QueryRow(`SELECT used_at FROM password_reset_tokens WHERE token_hash = ?`,
		services.HashForValidation(raw)).Scan(&used); err != nil {
		t.Fatalf("reload token: %v", err)
	}
	if used.Valid {
		t.Fatal("rejected request consumed the reset token")
	}
}
