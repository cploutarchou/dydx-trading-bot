package services

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

func setupCodexCredentialService(t *testing.T) *ExternalAPICredentialService {
	t.Helper()
	t.Setenv("ENCRYPTION_KEY", "codex-service-test-encryption-key!")

	dbConn, err := sql.Open("sqlite", "file:codex-service-test?mode=memory&cache=shared")
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

	return NewExternalAPICredentialService(repository.NewExternalAPICredentialRepository(dbConn))
}

func TestCodexServiceStatusPrefersUserKeyOverSharedKey(t *testing.T) {
	credentialService := setupCodexCredentialService(t)
	if _, err := credentialService.Save(42, ExternalAPIProviderCodexIO, "user-codex-key", "personal"); err != nil {
		t.Fatalf("save credential: %v", err)
	}

	service := &CodexService{
		baseURL:      defaultCodexBaseURL,
		credentials:  credentialService,
		sharedAPIKey: "shared-codex-key",
		limiter:      newSerialRateLimiter(defaultCodexRequestsPerSecond),
		cache:        make(map[string]cacheEntry),
	}

	status, err := service.Status(42)
	if err != nil {
		t.Fatalf("Status returned error: %v", err)
	}
	if !status.Configured {
		t.Fatal("expected configured status")
	}
	if status.ActiveKeySource != "user" {
		t.Fatalf("expected user key to win, got %q", status.ActiveKeySource)
	}
	if !status.SharedKeyAvailable || !status.UserKeyAvailable {
		t.Fatalf("expected both shared and user keys to be available: %+v", status)
	}
}

func TestCodexServiceStatusReportsMissingConfiguration(t *testing.T) {
	service := &CodexService{
		baseURL: defaultCodexBaseURL,
		limiter: newSerialRateLimiter(defaultCodexRequestsPerSecond),
		cache:   make(map[string]cacheEntry),
	}

	status, err := service.Status(7)
	if err != nil {
		t.Fatalf("Status returned error: %v", err)
	}
	if status.Configured {
		t.Fatal("expected configured=false")
	}
	if !strings.Contains(status.Message, "CODEX_IO_API_KEY") {
		t.Fatalf("expected setup guidance in message, got %q", status.Message)
	}
}

func TestCodexServiceSearchUsesCacheAndNormalizesResults(t *testing.T) {
	var requests int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&requests, 1)
		if got := r.Header.Get("Authorization"); got != "shared-codex-key" {
			t.Fatalf("unexpected Authorization header: %q", got)
		}
		if got := r.Header.Get("X-Trace-Id"); got != "trace-codex-search" {
			t.Fatalf("unexpected trace header: %q", got)
		}

		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request: %v", err)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"data": {
				"filterTokens": {
					"results": [
						{
							"token": {
								"id": "0xeth:1",
								"address": "0xeth",
								"networkId": 1,
								"name": "Ether",
								"symbol": "ETH",
								"isScam": false
							},
							"priceUSD": "3200.5",
							"change1": "0.012",
							"change4": "0.018",
							"change24": "0.085",
							"liquidity": "500000",
							"volume24": "1200000",
							"marketCap": "2500000000",
							"txnCount24": 870,
							"exchanges": [{"name": "Uniswap"}]
						}
					]
				}
			}
		}`))
	}))
	defer upstream.Close()

	service := &CodexService{
		baseURL:      upstream.URL,
		httpClient:   upstream.Client(),
		sharedAPIKey: "shared-codex-key",
		limiter:      newSerialRateLimiter(1000),
		cache:        make(map[string]cacheEntry),
	}

	first, err := service.SearchTokens(context.Background(), 5, "ETH", nil, 5, "trace-codex-search")
	if err != nil {
		t.Fatalf("SearchTokens returned error: %v", err)
	}
	second, err := service.SearchTokens(context.Background(), 5, "ETH", nil, 5, "trace-codex-search")
	if err != nil {
		t.Fatalf("SearchTokens cached call returned error: %v", err)
	}

	if atomic.LoadInt32(&requests) != 1 {
		t.Fatalf("expected one upstream request due to cache, got %d", requests)
	}
	if len(first) != 1 || len(second) != 1 {
		t.Fatalf("expected one token result, got %d and %d", len(first), len(second))
	}
	if first[0].Symbol != "ETH" || first[0].PriceChangePct24H != 8.5 {
		t.Fatalf("unexpected normalized token result: %+v", first[0])
	}
}

func TestCodexServiceExecuteQueryMapsUnauthorized(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"errors":[{"message":"invalid key"}]}`))
	}))
	defer upstream.Close()

	service := &CodexService{
		baseURL:    upstream.URL,
		httpClient: upstream.Client(),
		limiter:    newSerialRateLimiter(1000),
		cache:      make(map[string]cacheEntry),
	}

	err := service.executeQuery(context.Background(), "bad-key", "trace-codex-401", "query { getNetworks { id } }", nil, &map[string]any{})
	if err == nil {
		t.Fatal("expected executeQuery to fail")
	}

	var serviceErr *CodexServiceError
	if !strings.Contains(err.Error(), "rejected") || !errors.As(err, &serviceErr) || serviceErr.StatusCode() != http.StatusUnauthorized {
		t.Fatalf("unexpected error: %#v", err)
	}
}
