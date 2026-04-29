package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func setupAIMarketRouter(t *testing.T) (*gin.Engine, string) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("ENCRYPTION_KEY", "ai-market-route-test-encryption-key!")

	const jwtSecret = "ai-market-route-secret"
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             jwtSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", "file:ai-market-route-test?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })

	if _, err := dbConn.Exec(`
		CREATE TABLE external_api_credentials (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			provider TEXT NOT NULL,
			label TEXT NOT NULL DEFAULT '',
			encrypted_api_key TEXT NOT NULL,
			api_key_hash TEXT NOT NULL DEFAULT '',
			api_key_masked TEXT NOT NULL DEFAULT '',
			is_active BOOLEAN NOT NULL DEFAULT 1,
			created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE (user_id, provider)
		)
	`); err != nil {
		t.Fatalf("create credentials table: %v", err)
	}

	manager := auth.NewManager(auth.JWTConfig{
		Secret:            jwtSecret,
		ExpiryHours:       1,
		RefreshExpiryDays: 7,
	})
	token, _, err := manager.CreateAccessToken(1, "ai-user", "ai@example.local", false)
	if err != nil {
		t.Fatalf("create access token: %v", err)
	}

	router := gin.New()
	RegisterAIMarketRoutes(router, &backenddb.Database{DB: dbConn}, nil)
	return router, token
}

func TestAIMarketRoutes_KeyLifecycle(t *testing.T) {
	router, token := setupAIMarketRouter(t)

	saveBody := bytes.NewBufferString(`{"provider":"deepseek","api_key":"user-deepseek-key","label":"DeepSeek personal"}`)
	saveRequest := httptest.NewRequest(http.MethodPut, "/api/v1/ai/market-filters/key", saveBody)
	saveRequest.Header.Set("Authorization", "Bearer "+token)
	saveRequest.Header.Set("Content-Type", "application/json")
	saveResponse := httptest.NewRecorder()
	router.ServeHTTP(saveResponse, saveRequest)
	if saveResponse.Code != http.StatusOK {
		t.Fatalf("expected key save 200, got %d body=%s", saveResponse.Code, saveResponse.Body.String())
	}

	statusRequest := httptest.NewRequest(http.MethodGet, "/api/v1/ai/market-filters/status", nil)
	statusRequest.Header.Set("Authorization", "Bearer "+token)
	statusResponse := httptest.NewRecorder()
	router.ServeHTTP(statusResponse, statusRequest)
	if statusResponse.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d body=%s", statusResponse.Code, statusResponse.Body.String())
	}

	var statusEnvelope struct {
		Success bool `json:"success"`
		Data    struct {
			Providers []struct {
				Provider         string `json:"provider"`
				UserKeyAvailable bool   `json:"user_key_available"`
				ActiveKeySource  string `json:"active_key_source"`
			} `json:"providers"`
		} `json:"data"`
	}
	if err := json.Unmarshal(statusResponse.Body.Bytes(), &statusEnvelope); err != nil {
		t.Fatalf("decode status response: %v", err)
	}

	foundDeepSeek := false
	for _, provider := range statusEnvelope.Data.Providers {
		if provider.Provider == "deepseek" {
			foundDeepSeek = true
			if !provider.UserKeyAvailable || provider.ActiveKeySource != "user" {
				t.Fatalf("expected DeepSeek user key to be active, got %+v", provider)
			}
		}
	}
	if !foundDeepSeek {
		t.Fatalf("expected DeepSeek status in providers: %+v", statusEnvelope.Data.Providers)
	}

	deleteRequest := httptest.NewRequest(http.MethodDelete, "/api/v1/ai/market-filters/key/deepseek", nil)
	deleteRequest.Header.Set("Authorization", "Bearer "+token)
	deleteResponse := httptest.NewRecorder()
	router.ServeHTTP(deleteResponse, deleteRequest)
	if deleteResponse.Code != http.StatusOK {
		t.Fatalf("expected delete 200, got %d body=%s", deleteResponse.Code, deleteResponse.Body.String())
	}
}
