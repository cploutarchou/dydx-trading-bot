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
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func setupRegistrationRouter(t *testing.T) (*gin.Engine, *sql.DB) {
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
		full_name TEXT,
		avatar TEXT,
		hashed_password TEXT NOT NULL,
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
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
	RegisterAuthRoutes(router, dbConn)
	return router, dbConn
}

func TestRegistrationStatus_DefaultsEnabled(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	defer dbConn.Close()

	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/registration-status", nil)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Data struct {
			Enabled bool `json:"enabled"`
		} `json:"data"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !body.Data.Enabled {
		t.Fatalf("expected public registration enabled by default")
	}
}

func TestRegister_ForbiddenWhenPublicRegistrationDisabled(t *testing.T) {
	router, dbConn := setupRegistrationRouter(t)
	defer dbConn.Close()

	if _, err := dbConn.Exec(
		`INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"platform",
		"allow_public_registration",
		"false",
		"boolean",
		"Allow public registration",
		"true",
		true,
		1,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert bot setting: %v", err)
	}

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
