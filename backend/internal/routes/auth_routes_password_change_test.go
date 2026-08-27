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
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupPasswordChangeRouter(t *testing.T) (*gin.Engine, *sql.DB) {
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

	router := gin.New()
	RegisterAuthRoutes(router, dbConn)
	return router, dbConn
}

func TestChangePassword_ClearsRotationRequirement(t *testing.T) {
	router, dbConn := setupPasswordChangeRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	hashedPassword, err := bcrypt.GenerateFromPassword([]byte("TempPass123"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("hash password: %v", err)
	}

	now := time.Now().UTC()
	_, err = dbConn.Exec(
		`INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, password_change_required, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"admin",
		"admin@example.local",
		"admin",
		"Administrator",
		"",
		string(hashedPassword),
		true,
		true,
		true,
		now,
		now,
	)
	if err != nil {
		t.Fatalf("seed user: %v", err)
	}
	var insertID int
	if err := dbConn.QueryRow(`SELECT id FROM users WHERE username = ?`, "admin").Scan(&insertID); err != nil {
		t.Fatalf("lookup inserted user id: %v", err)
	}

	token, err := services.GenerateAccessTokenWithRole(int(insertID), "admin", true, "admin")
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}

	payload, _ := json.Marshal(map[string]string{
		"current_password": "TempPass123",
		"new_password":     "NewPass123!",
	})
	req := httptest.NewRequest(http.MethodPut, "/api/v1/auth/change-password", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var passwordHash string
	var passwordChangeRequired bool
	if err := dbConn.QueryRow(`SELECT hashed_password, password_change_required FROM users WHERE id = ?`, insertID).Scan(&passwordHash, &passwordChangeRequired); err != nil {
		t.Fatalf("reload user: %v", err)
	}

	if passwordChangeRequired {
		t.Fatalf("expected password_change_required=false")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(passwordHash), []byte("NewPass123!")); err != nil {
		t.Fatalf("expected updated password hash, compare error: %v", err)
	}
}
