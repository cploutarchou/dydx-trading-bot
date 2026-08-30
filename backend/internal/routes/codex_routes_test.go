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
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

func setupCodexRouter(t *testing.T, upstream http.Handler) (*gin.Engine, string) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	upstreamServer := httptest.NewServer(upstream)
	t.Cleanup(upstreamServer.Close)

	t.Setenv("CODEX_IO_API_KEY", "shared-codex-key")
	t.Setenv("CODEX_IO_BASE_URL", upstreamServer.URL)
	t.Setenv("ENCRYPTION_KEY", "codex-route-test-encryption-key!")

	const jwtSecret = "codex-route-secret"
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             jwtSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", "file:codex-route-test?mode=memory&cache=shared")
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
			api_key_salt TEXT NOT NULL DEFAULT '',
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
	token, _, err := manager.CreateAccessToken(1, "codex-user", "codex@example.local", false)
	if err != nil {
		t.Fatalf("create access token: %v", err)
	}

	router := gin.New()
	RegisterCodexRoutes(router, &backenddb.Database{DB: dbConn})
	return router, token
}

func TestCodexRoutes_StatusAndKeyLifecycle(t *testing.T) {
	router, token := setupCodexRouter(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":{"filterTokens":{"results":[]}}}`))
	}))

	request := httptest.NewRequest(http.MethodGet, "/api/v1/codex/status", nil)
	request.Header.Set("Authorization", "Bearer "+token)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("expected 200 status, got %d", response.Code)
	}

	var statusEnvelope struct {
		Success bool `json:"success"`
		Data    struct {
			Provider           string `json:"provider"`
			ActiveKeySource    string `json:"active_key_source"`
			SharedKeyAvailable bool   `json:"shared_key_available"`
			UserKeyAvailable   bool   `json:"user_key_available"`
		} `json:"data"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &statusEnvelope); err != nil {
		t.Fatalf("decode status response: %v", err)
	}
	if !statusEnvelope.Success || statusEnvelope.Data.Provider != "codex.io" || statusEnvelope.Data.ActiveKeySource != "shared" {
		t.Fatalf("unexpected initial status payload: %+v", statusEnvelope)
	}

	saveBody := bytes.NewBufferString(`{"api_key":"user-codex-key","label":"Personal free plan"}`)
	saveRequest := httptest.NewRequest(http.MethodPut, "/api/v1/codex/key", saveBody)
	saveRequest.Header.Set("Authorization", "Bearer "+token)
	saveRequest.Header.Set("Content-Type", "application/json")
	saveResponse := httptest.NewRecorder()
	router.ServeHTTP(saveResponse, saveRequest)
	if saveResponse.Code != http.StatusOK {
		t.Fatalf("expected key save 200, got %d body=%s", saveResponse.Code, saveResponse.Body.String())
	}

	statusAfterSave := httptest.NewRequest(http.MethodGet, "/api/v1/codex/status", nil)
	statusAfterSave.Header.Set("Authorization", "Bearer "+token)
	statusAfterSaveRecorder := httptest.NewRecorder()
	router.ServeHTTP(statusAfterSaveRecorder, statusAfterSave)
	if err := json.Unmarshal(statusAfterSaveRecorder.Body.Bytes(), &statusEnvelope); err != nil {
		t.Fatalf("decode updated status response: %v", err)
	}
	if statusEnvelope.Data.ActiveKeySource != "user" || !statusEnvelope.Data.UserKeyAvailable {
		t.Fatalf("expected user key to become active, got %+v", statusEnvelope.Data)
	}

	deleteRequest := httptest.NewRequest(http.MethodDelete, "/api/v1/codex/key", nil)
	deleteRequest.Header.Set("Authorization", "Bearer "+token)
	deleteResponse := httptest.NewRecorder()
	router.ServeHTTP(deleteResponse, deleteRequest)
	if deleteResponse.Code != http.StatusOK {
		t.Fatalf("expected key delete 200, got %d", deleteResponse.Code)
	}

	statusAfterDelete := httptest.NewRequest(http.MethodGet, "/api/v1/codex/status", nil)
	statusAfterDelete.Header.Set("Authorization", "Bearer "+token)
	statusAfterDeleteRecorder := httptest.NewRecorder()
	router.ServeHTTP(statusAfterDeleteRecorder, statusAfterDelete)
	if err := json.Unmarshal(statusAfterDeleteRecorder.Body.Bytes(), &statusEnvelope); err != nil {
		t.Fatalf("decode deleted status response: %v", err)
	}
	if statusEnvelope.Data.ActiveKeySource != "shared" || statusEnvelope.Data.UserKeyAvailable {
		t.Fatalf("expected shared fallback after delete, got %+v", statusEnvelope.Data)
	}
}

func TestCodexRoutes_OverviewNormalizesMarketData(t *testing.T) {
	router, token := setupCodexRouter(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "shared-codex-key" {
			t.Fatalf("unexpected Authorization header: %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"data": {
				"movers": {
					"results": [
						{
							"token": {"id":"0xeth:1","address":"0xeth","networkId":1,"name":"Ether","symbol":"ETH","isScam":false},
							"priceUSD":"3200",
							"change1":"0.01",
							"change4":"0.02",
							"change24":"0.09",
							"liquidity":"600000",
							"volume24":"1500000",
							"marketCap":"1000000000",
							"txnCount24":900,
							"exchanges":[{"name":"Uniswap"}]
						}
					]
				},
				"safe": {
					"results": [
						{
							"token": {"id":"0xbtc:1","address":"0xbtc","networkId":1,"name":"Wrapped BTC","symbol":"WBTC","isScam":false},
							"priceUSD":"70000",
							"change1":"0.002",
							"change4":"0.004",
							"change24":"0.012",
							"liquidity":"2500000",
							"volume24":"5000000",
							"marketCap":"9000000000",
							"txnCount24":1200,
							"exchanges":[{"name":"Uniswap"}]
						}
					]
				}
			}
		}`))
	}))

	request := httptest.NewRequest(http.MethodGet, "/api/v1/codex/market/overview?network=1&limit=3", nil)
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("X-Trace-Id", "route-overview-trace")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("expected overview 200, got %d body=%s", response.Code, response.Body.String())
	}

	var envelope struct {
		Success bool `json:"success"`
		Data    struct {
			NetworkID int `json:"network_id"`
			Movers    []struct {
				Symbol            string  `json:"symbol"`
				PriceChangePct24H float64 `json:"price_change_pct_24h"`
			} `json:"movers"`
			SafeMovers []struct {
				ConfidenceHint string `json:"confidence_hint"`
			} `json:"safe_movers"`
			GeneratedAt string `json:"generated_at"`
		} `json:"data"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode overview response: %v", err)
	}
	if !envelope.Success || envelope.Data.NetworkID != 1 || len(envelope.Data.Movers) != 1 {
		t.Fatalf("unexpected overview payload: %+v", envelope)
	}
	if envelope.Data.Movers[0].Symbol != "ETH" || envelope.Data.Movers[0].PriceChangePct24H != 9 {
		t.Fatalf("unexpected mover normalization: %+v", envelope.Data.Movers[0])
	}
	if len(envelope.Data.SafeMovers) != 1 || envelope.Data.SafeMovers[0].ConfidenceHint != "high" {
		t.Fatalf("unexpected safe mover payload: %+v", envelope.Data.SafeMovers)
	}
	if _, err := time.Parse(time.RFC3339, envelope.Data.GeneratedAt); err != nil {
		t.Fatalf("expected generated_at RFC3339 timestamp, got %q", envelope.Data.GeneratedAt)
	}
}
