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
	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
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
	if err := config.LoadConfig(); err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
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
			api_key_salt TEXT NOT NULL DEFAULT '',
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

func seedTelegramUser(t *testing.T, dbConn *sql.DB, username string, email string, role string, isAdmin bool) string {
	t.Helper()
	_, authHeader := seedTelegramUserWithID(t, dbConn, username, email, role, isAdmin)
	return authHeader
}

func seedTelegramUserWithID(t *testing.T, dbConn *sql.DB, username string, email string, role string, isAdmin bool) (int, string) {
	t.Helper()
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte("Pass123!"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("hash password: %v", err)
	}
	now := time.Now().UTC()
	_, err = dbConn.Exec(
		`INSERT INTO users (username, email, role, full_name, avatar, hashed_password, is_active, is_admin, password_change_required, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		username,
		email,
		role,
		"Administrator",
		"",
		string(hashedPassword),
		true,
		isAdmin,
		true,
		now,
		now,
	)
	if err != nil {
		t.Fatalf("seed admin: %v", err)
	}
	var insertID int
	if err := dbConn.QueryRow(`SELECT id FROM users WHERE username = ?`, username).Scan(&insertID); err != nil {
		t.Fatalf("lookup inserted user id: %v", err)
	}
	token, err := services.GenerateAccessTokenWithRole(int(insertID), role, isAdmin, role)
	if err != nil {
		t.Fatalf("generate token: %v", err)
	}
	return int(insertID), "Bearer " + token
}

func TestTelegramRoutes_SaveAndStatus(t *testing.T) {
	router, dbConn := setupTelegramRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	authHeader := seedTelegramUser(t, dbConn, "client1", "client1@example.local", "client", false)

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

func TestTelegramRoutes_IsolatedPerUser(t *testing.T) {
	router, dbConn := setupTelegramRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	userOneAuth := seedTelegramUser(t, dbConn, "client_a", "client_a@example.local", "client", false)
	userTwoAuth := seedTelegramUser(t, dbConn, "client_b", "client_b@example.local", "client", false)

	payload, _ := json.Marshal(map[string]string{
		"bot_token": "123456:user-a-token",
		"chat_id":   "-1001111111111",
		"label":     "User A alerts",
	})

	saveReq := httptest.NewRequest(http.MethodPut, "/api/v1/telegram/config", bytes.NewReader(payload))
	saveReq.Header.Set("Content-Type", "application/json")
	saveReq.Header.Set("Authorization", userOneAuth)
	saveRes := httptest.NewRecorder()
	router.ServeHTTP(saveRes, saveReq)
	if saveRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for user one save, got %d body=%s", saveRes.Code, saveRes.Body.String())
	}

	statusReqUserOne := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/status", nil)
	statusReqUserOne.Header.Set("Authorization", userOneAuth)
	statusResUserOne := httptest.NewRecorder()
	router.ServeHTTP(statusResUserOne, statusReqUserOne)
	if statusResUserOne.Code != http.StatusOK {
		t.Fatalf("expected 200 for user one status, got %d body=%s", statusResUserOne.Code, statusResUserOne.Body.String())
	}

	statusReqUserTwo := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/status", nil)
	statusReqUserTwo.Header.Set("Authorization", userTwoAuth)
	statusResUserTwo := httptest.NewRecorder()
	router.ServeHTTP(statusResUserTwo, statusReqUserTwo)
	if statusResUserTwo.Code != http.StatusOK {
		t.Fatalf("expected 200 for user two status, got %d body=%s", statusResUserTwo.Code, statusResUserTwo.Body.String())
	}

	var userOneBody struct {
		Data struct {
			Configured bool   `json:"configured"`
			ChatID     string `json:"chat_id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(statusResUserOne.Body.Bytes(), &userOneBody); err != nil {
		t.Fatalf("decode user one response: %v", err)
	}

	if !userOneBody.Data.Configured || userOneBody.Data.ChatID != "-1001111111111" {
		t.Fatalf("unexpected user one telegram state: %+v", userOneBody.Data)
	}

	var userTwoBody struct {
		Data struct {
			Configured bool   `json:"configured"`
			ChatID     string `json:"chat_id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(statusResUserTwo.Body.Bytes(), &userTwoBody); err != nil {
		t.Fatalf("decode user two response: %v", err)
	}

	if userTwoBody.Data.Configured || userTwoBody.Data.ChatID != "" {
		t.Fatalf("expected user two to remain unconfigured, got %+v", userTwoBody.Data)
	}
}

func TestTelegramRoutes_AdminSelfServiceScope(t *testing.T) {
	router, dbConn := setupTelegramRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminAuth := seedTelegramUser(t, dbConn, "admin_scope", "admin_scope@example.local", "admin", true)
	clientAuth := seedTelegramUser(t, dbConn, "client_scope", "client_scope@example.local", "client", false)

	adminSaveReq := httptest.NewRequest(http.MethodPut, "/api/v1/telegram/config", bytes.NewReader([]byte(`{"bot_token":"x","chat_id":"-1001"}`)))
	adminSaveReq.Header.Set("Content-Type", "application/json")
	adminSaveReq.Header.Set("Authorization", adminAuth)
	adminSaveRes := httptest.NewRecorder()
	router.ServeHTTP(adminSaveRes, adminSaveReq)
	if adminSaveRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for admin save, got %d body=%s", adminSaveRes.Code, adminSaveRes.Body.String())
	}

	adminStatusReq := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/status", nil)
	adminStatusReq.Header.Set("Authorization", adminAuth)
	adminStatusRes := httptest.NewRecorder()
	router.ServeHTTP(adminStatusRes, adminStatusReq)
	if adminStatusRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for admin status, got %d body=%s", adminStatusRes.Code, adminStatusRes.Body.String())
	}

	clientStatusReq := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/status", nil)
	clientStatusReq.Header.Set("Authorization", clientAuth)
	clientStatusRes := httptest.NewRecorder()
	router.ServeHTTP(clientStatusRes, clientStatusReq)
	if clientStatusRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for client status, got %d body=%s", clientStatusRes.Code, clientStatusRes.Body.String())
	}

	var adminBody struct {
		Data struct {
			Configured   bool   `json:"configured"`
			ChatID       string `json:"chat_id"`
			DeliveryMode string `json:"delivery_mode"`
		} `json:"data"`
	}
	if err := json.Unmarshal(adminStatusRes.Body.Bytes(), &adminBody); err != nil {
		t.Fatalf("decode admin status response: %v", err)
	}

	if !adminBody.Data.Configured || adminBody.Data.ChatID != "-1001" {
		t.Fatalf("unexpected admin telegram self-service state: %+v", adminBody.Data)
	}
	if adminBody.Data.DeliveryMode != "user" {
		t.Fatalf("expected admin delivery_mode=user, got %q", adminBody.Data.DeliveryMode)
	}

	var clientBody struct {
		Data struct {
			Configured bool   `json:"configured"`
			ChatID     string `json:"chat_id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(clientStatusRes.Body.Bytes(), &clientBody); err != nil {
		t.Fatalf("decode client status response: %v", err)
	}

	if clientBody.Data.Configured || clientBody.Data.ChatID != "" {
		t.Fatalf("expected client to remain unconfigured when only admin self config is set, got %+v", clientBody.Data)
	}
}

func TestTelegramRoutes_GlobalScopeRequiresAdminAndFallsBackForRuntime(t *testing.T) {
	router, dbConn := setupTelegramRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminAuth := seedTelegramUser(t, dbConn, "admin_global", "admin_global@example.local", "admin", true)
	clientID, clientAuth := seedTelegramUserWithID(t, dbConn, "client_global", "client_global@example.local", "client", false)

	forbiddenReq := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/global/status", nil)
	forbiddenReq.Header.Set("Authorization", clientAuth)
	forbiddenRes := httptest.NewRecorder()
	router.ServeHTTP(forbiddenRes, forbiddenReq)
	if forbiddenRes.Code != http.StatusForbidden {
		t.Fatalf("expected 403 for client global status, got %d body=%s", forbiddenRes.Code, forbiddenRes.Body.String())
	}

	globalPayload, _ := json.Marshal(map[string]string{
		"bot_token": "123456:global-token",
		"chat_id":   "-1009999999999",
		"label":     "Platform alerts",
	})
	saveReq := httptest.NewRequest(http.MethodPut, "/api/v1/telegram/global/config", bytes.NewReader(globalPayload))
	saveReq.Header.Set("Content-Type", "application/json")
	saveReq.Header.Set("Authorization", adminAuth)
	saveRes := httptest.NewRecorder()
	router.ServeHTTP(saveRes, saveReq)
	if saveRes.Code != http.StatusOK {
		t.Fatalf("expected 200 saving global config, got %d body=%s", saveRes.Code, saveRes.Body.String())
	}

	userStatusReq := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/user/status", nil)
	userStatusReq.Header.Set("Authorization", clientAuth)
	userStatusRes := httptest.NewRecorder()
	router.ServeHTTP(userStatusRes, userStatusReq)
	if userStatusRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for client user status, got %d body=%s", userStatusRes.Code, userStatusRes.Body.String())
	}

	var userStatus struct {
		Data struct {
			Configured bool   `json:"configured"`
			ChatID     string `json:"chat_id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(userStatusRes.Body.Bytes(), &userStatus); err != nil {
		t.Fatalf("decode user status: %v", err)
	}
	if userStatus.Data.Configured || userStatus.Data.ChatID != "" {
		t.Fatalf("expected global config not to appear in personal status, got %+v", userStatus.Data)
	}

	credentialRepo := repository.NewExternalAPICredentialRepository(dbConn)
	settingsRepo := repository.NewSettingsRepository(dbConn)
	telegramService := services.NewTelegramService(services.NewExternalAPICredentialService(credentialRepo), settingsRepo)
	resolved, err := telegramService.ResolveEffectiveConfig(clientID)
	if err != nil {
		t.Fatalf("resolve effective config: %v", err)
	}
	if resolved == nil || resolved.Source != services.TelegramConfigSourceGlobal || resolved.Config == nil {
		t.Fatalf("expected effective config to fall back to global, got %+v", resolved)
	}
	if resolved.Config.ChatID != "-1009999999999" || resolved.Config.BotToken != "123456:global-token" {
		t.Fatalf("unexpected effective global config: %+v", resolved.Config)
	}
}

func TestTelegramRoutes_PreflightValidation(t *testing.T) {
	router, dbConn := setupTelegramRouter(t)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	userAuth := seedTelegramUser(t, dbConn, "preflight_user", "preflight_user@example.local", "client", false)

	// Test 1: Preflight with missing config (empty body) should return validation failure
	preflightReq := httptest.NewRequest(http.MethodPost, "/api/v1/telegram/preflight", bytes.NewReader([]byte(`{}`)))
	preflightReq.Header.Set("Authorization", userAuth)
	preflightReq.Header.Set("Content-Type", "application/json")
	preflightRes := httptest.NewRecorder()
	router.ServeHTTP(preflightRes, preflightReq)
	if preflightRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for preflight validation, got %d body=%s", preflightRes.Code, preflightRes.Body.String())
	}

	var emptyBody struct {
		Data struct {
			Valid bool   `json:"valid"`
			Error string `json:"error"`
		} `json:"data"`
	}
	if err := json.Unmarshal(preflightRes.Body.Bytes(), &emptyBody); err != nil {
		t.Fatalf("decode empty token response: %v", err)
	}

	if emptyBody.Data.Valid {
		t.Fatalf("expected validation to fail for empty token/chat, got valid=true")
	}

	// Test 2: Preflight with invalid token override should fail validation gracefully
	invalidTokenPayload, _ := json.Marshal(map[string]string{
		"bot_token": "invalid:token",
		"chat_id":   "-100123450001",
	})
	invalidReq := httptest.NewRequest(http.MethodPost, "/api/v1/telegram/preflight", bytes.NewReader(invalidTokenPayload))
	invalidReq.Header.Set("Authorization", userAuth)
	invalidReq.Header.Set("Content-Type", "application/json")
	invalidRes := httptest.NewRecorder()
	router.ServeHTTP(invalidRes, invalidReq)
	if invalidRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for invalid token preflight, got %d body=%s", invalidRes.Code, invalidRes.Body.String())
	}

	var invalidBody struct {
		Data struct {
			Valid            bool   `json:"valid"`
			Error            string `json:"error"`
			ValidationReason string `json:"validation_reason"`
		} `json:"data"`
	}
	if err := json.Unmarshal(invalidRes.Body.Bytes(), &invalidBody); err != nil {
		t.Fatalf("decode invalid token response: %v", err)
	}

	if invalidBody.Data.Valid {
		t.Fatalf("expected validation to fail for invalid token, got %+v", invalidBody.Data)
	}
	if !strings.Contains(strings.ToLower(invalidBody.Data.Error), "invalid") {
		t.Fatalf("expected validation error to mention invalid token, got %q", invalidBody.Data.Error)
	}

	// Test 3: Invalid token override should NOT be saved to DB
	statusReq := httptest.NewRequest(http.MethodGet, "/api/v1/telegram/status", nil)
	statusReq.Header.Set("Authorization", userAuth)
	statusRes := httptest.NewRecorder()
	router.ServeHTTP(statusRes, statusReq)
	if statusRes.Code != http.StatusOK {
		t.Fatalf("expected 200 for status check, got %d", statusRes.Code)
	}

	var statusBody struct {
		Data struct {
			Configured bool   `json:"configured"`
			ChatID     string `json:"chat_id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(statusRes.Body.Bytes(), &statusBody); err != nil {
		t.Fatalf("decode status response: %v", err)
	}

	if statusBody.Data.Configured {
		t.Fatalf("expected invalid token NOT to be saved, but status shows configured=true")
	}
}
