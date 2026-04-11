//go:build integration

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

func setupNewsRouter(t *testing.T, upstream http.Handler) (*gin.Engine, string, string) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	upstreamServer := httptest.NewServer(upstream)
	t.Cleanup(upstreamServer.Close)
	t.Setenv("COINDESK_RSS_URL", upstreamServer.URL)
	t.Setenv("ENCRYPTION_KEY", "news-route-test-encryption-key!!!")

	const jwtSecret = "news-route-secret"
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             jwtSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", "file:news-route-test?mode=memory&cache=shared")
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

	manager := auth.NewManager(auth.JWTConfig{Secret: jwtSecret, ExpiryHours: 1, RefreshExpiryDays: 7})
	adminToken, _, err := manager.CreateAccessToken(1, "admin", "admin@example.local", true)
	if err != nil {
		t.Fatalf("create admin token: %v", err)
	}
	userToken, _, err := manager.CreateAccessToken(2, "user", "user@example.local", false)
	if err != nil {
		t.Fatalf("create user token: %v", err)
	}

	router := gin.New()
	RegisterNewsRoutes(router, &backenddb.Database{DB: dbConn})
	return router, adminToken, userToken
}

func TestNewsRoutes_AdminConfigAndUserRead(t *testing.T) {
	router, adminToken, userToken := setupNewsRouter(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/xml")
		_, _ = w.Write([]byte(`<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel>
    <lastBuildDate>Sun, 05 Apr 2026 14:05:46 +0000</lastBuildDate>
    <item>
      <title><![CDATA[Headline]]></title>
      <link>https://www.coindesk.com/story</link>
      <guid isPermaLink="false">story-1</guid>
      <pubDate>Sun, 05 Apr 2026 14:00:00 +0000</pubDate>
      <description><![CDATA[Summary]]></description>
      <dc:creator>Reporter</dc:creator>
      <category>Markets</category>
    </item>
  </channel>
</rss>`))
	}))

	saveReq := httptest.NewRequest(http.MethodPut, "/api/v1/news/coindesk/config", bytes.NewBufferString(`{"api_key":"shared-news-key","label":"Admin key"}`))
	saveReq.Header.Set("Authorization", "Bearer "+adminToken)
	saveReq.Header.Set("Content-Type", "application/json")
	saveResp := httptest.NewRecorder()
	router.ServeHTTP(saveResp, saveReq)
	if saveResp.Code != http.StatusOK {
		t.Fatalf("expected config save 200, got %d body=%s", saveResp.Code, saveResp.Body.String())
	}

	statusReq := httptest.NewRequest(http.MethodGet, "/api/v1/news/coindesk/config", nil)
	statusReq.Header.Set("Authorization", "Bearer "+adminToken)
	statusResp := httptest.NewRecorder()
	router.ServeHTTP(statusResp, statusReq)
	if statusResp.Code != http.StatusOK {
		t.Fatalf("expected config status 200, got %d body=%s", statusResp.Code, statusResp.Body.String())
	}

	var statusEnvelope struct {
		Data struct {
			SharedKeyPresent bool `json:"shared_key_present"`
		} `json:"data"`
	}
	if err := json.Unmarshal(statusResp.Body.Bytes(), &statusEnvelope); err != nil {
		t.Fatalf("decode status response: %v", err)
	}
	if !statusEnvelope.Data.SharedKeyPresent {
		t.Fatalf("expected shared key present, got %+v", statusEnvelope)
	}

	newsReq := httptest.NewRequest(http.MethodGet, "/api/v1/news/coindesk?limit=2", nil)
	newsReq.Header.Set("Authorization", "Bearer "+userToken)
	newsResp := httptest.NewRecorder()
	router.ServeHTTP(newsResp, newsReq)
	if newsResp.Code != http.StatusOK {
		t.Fatalf("expected news 200, got %d body=%s", newsResp.Code, newsResp.Body.String())
	}

	var newsEnvelope struct {
		Data struct {
			Articles []struct {
				Title string `json:"title"`
			} `json:"articles"`
		} `json:"data"`
	}
	if err := json.Unmarshal(newsResp.Body.Bytes(), &newsEnvelope); err != nil {
		t.Fatalf("decode news response: %v", err)
	}
	if len(newsEnvelope.Data.Articles) != 1 || newsEnvelope.Data.Articles[0].Title != "Headline" {
		t.Fatalf("unexpected news payload: %+v", newsEnvelope)
	}
}
