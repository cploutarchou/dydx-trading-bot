package middleware

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

const comingSoonTestJWTSecret = "coming-soon-test-jwt-secret-32!!"

func setupComingSoonMiddlewareTest(t *testing.T, enabled bool) (*gin.Engine, *sql.DB, string, string) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             comingSoonTestJWTSecret,
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
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
		updated_at DATETIME NOT NULL,
		UNIQUE(section, key)
	);`); err != nil {
		t.Fatalf("create bot_settings table: %v", err)
	}

	value := "false"
	if enabled {
		value = "true"
	}
	if _, err := dbConn.Exec(
		`INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		"platform",
		"coming_soon_enabled",
		value,
		"boolean",
		"Coming soon",
		"false",
		true,
		1,
		time.Now().UTC(),
		time.Now().UTC(),
	); err != nil {
		t.Fatalf("insert setting: %v", err)
	}

	manager := auth.NewManager(auth.JWTConfig{
		Secret:            comingSoonTestJWTSecret,
		ExpiryHours:       1,
		RefreshExpiryDays: 1,
	})
	userToken, _, err := manager.CreateAccessTokenWithRole(10, "client", "client@example.local", false, "client")
	if err != nil {
		t.Fatalf("create user token: %v", err)
	}
	adminToken, _, err := manager.CreateAccessTokenWithRole(1, "admin", "admin@example.local", true, "admin")
	if err != nil {
		t.Fatalf("create admin token: %v", err)
	}

	router := gin.New()
	router.Use(ComingSoonMiddleware(dbConn))
	router.GET("/api/v1/backtests", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"success": true})
	})
	router.GET("/api/v1/public/app-config", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"success": true})
	})

	return router, dbConn, userToken, adminToken
}

func TestComingSoonMiddlewareBlocksAuthenticatedNonAdmin(t *testing.T) {
	router, dbConn, userToken, _ := setupComingSoonMiddlewareTest(t, true)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/backtests", nil)
	req.Header.Set("Authorization", "Bearer "+userToken)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d body=%s", res.Code, res.Body.String())
	}

	var body struct {
		Code string `json:"code"`
	}
	if err := json.Unmarshal(res.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Code != "coming_soon_enabled" {
		t.Fatalf("expected coming_soon_enabled code, got %q", body.Code)
	}
}

func TestComingSoonMiddlewareAllowsAdminAndExemptRoutes(t *testing.T) {
	router, dbConn, _, adminToken := setupComingSoonMiddlewareTest(t, true)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	adminReq := httptest.NewRequest(http.MethodGet, "/api/v1/backtests", nil)
	adminReq.Header.Set("Authorization", "Bearer "+adminToken)
	adminRes := httptest.NewRecorder()
	router.ServeHTTP(adminRes, adminReq)
	if adminRes.Code != http.StatusOK {
		t.Fatalf("expected admin 200, got %d body=%s", adminRes.Code, adminRes.Body.String())
	}

	publicReq := httptest.NewRequest(http.MethodGet, "/api/v1/public/app-config", nil)
	publicRes := httptest.NewRecorder()
	router.ServeHTTP(publicRes, publicReq)
	if publicRes.Code != http.StatusOK {
		t.Fatalf("expected public config 200, got %d body=%s", publicRes.Code, publicRes.Body.String())
	}
}

func TestComingSoonMiddlewareAllowsWhenDisabled(t *testing.T) {
	router, dbConn, userToken, _ := setupComingSoonMiddlewareTest(t, false)
	t.Cleanup(func() {
		if err := dbConn.Close(); err != nil {
			t.Errorf("close db: %v", err)
		}
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/backtests", nil)
	req.Header.Set("Authorization", "Bearer "+userToken)
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)

	if res.Code != http.StatusOK {
		t.Fatalf("expected 200 when disabled, got %d body=%s", res.Code, res.Body.String())
	}
}
