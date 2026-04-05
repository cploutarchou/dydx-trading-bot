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
	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	_ "modernc.org/sqlite"
)

func setupTelegramRouter(t *testing.T) (*gin.Engine, *sql.DB) {
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

	statements := []string{
		`CREATE TABLE users (
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
		);`,
		`CREATE TABLE bot_settings (
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
		);`,
		`CREATE TABLE external_api_credentials (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			provider TEXT NOT NULL,
			label TEXT NOT NULL DEFAULT '',
			encrypted_api_key TEXT NOT NULL,
			api_key_hash TEXT NOT NULL DEFAULT '',
			api_key_masked TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT 1,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			CONSTRAINT uq_external_api_credentials_user_provider UNIQUE (user_id, provider)
		);`,
	}

	for _, statement := range statements {
		if _, err := dbConn.Exec(statement); err != nil {
			t.Fatalf("setup schema: %v", err)
		}
	}

	router := gin.New()
	RegisterTelegramRoutes(router, &backenddb.Database{DB: dbConn})
	return router, dbConn
}

func seedTelegramAdmin(t *testing.T, dbConn *sql.DB) string {
	t.Helper()
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("hash password: %v", err)
	}
	now := time.Now().UTC()
	result, err := dbConn.Exec(
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
		t.Fatalf("seed admin: %v", err)
	}
	insertID, err := result.LastInsertId()
	if err != nil {
		t.Fatalf("last insert id: %v", err)
	}
	token, err := services.GenerateAccessTokenWithRole(int(insertID), "admin", true, "admin")
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return "Bearer " + token
}

func TestTelegramRoutes_SaveAndStatus(t *testing.T) {
	router, dbConn := setupTelegramRouter(t)
	defer dbConn.Close()

	authHeader := seedTelegramAdmin(t, dbConn)

	payload, _ := json.Marshal(map[string]string{
		"bot_token": "123456:test-telegram-token",
		"chat_id":   "-1001234567890",
		"label":     "Primary alerts",
	})
	saveReq := httptest.NewRequest(http.MethodPut, "/api/v1/telegram/config", bytes.NewReader(payload))
	saveReq.Header.Set("Content-Type", "application/json")
	saveReq.Header.Set("Authorization", authHeader)
	saveRes := httptest.NewRecorder()
	router.ServeHTTP(saveRes, saveReq)

	if saveRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", saveRes.Code, saveRes.Body.String())
	}

	statusReq := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/status", nil)
	statusReq.Header.Set("Authorization", authHeader)
	statusRes := httptest.NewRecorder()
	router.ServeHTTP(statusRes, statusReq)

	if statusRes.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", statusRes.Code, statusRes.Body.String())
	}

	var body struct {
		Data struct {
			Configured         bool   `json:"configured"`
			SharedTokenPresent bool   `json:"shared_token_present"`
			ChatID             string `json:"chat_id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(statusRes.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}

	if !body.Data.Configured || !body.Data.SharedTokenPresent {
		t.Fatalf("expected telegram configured status")
	}
	if body.Data.ChatID != "-1001234567890" {
		t.Fatalf("unexpected telegram chat id: %+v", body.Data)
	}
}
