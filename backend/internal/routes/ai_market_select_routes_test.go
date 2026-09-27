package routes

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/dydx-trading-bot/backend-go/config"
	"github.com/dydx-trading-bot/backend-go/internal/auth"
	backenddb "github.com/dydx-trading-bot/backend-go/internal/db"
	"github.com/dydx-trading-bot/backend-go/internal/middleware"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

// setupAIMarketSelectRouter registers the AI routes with a bot client that
// points at botURL. It uses its own in-memory database name so it never
// shares state with setupAIMarketRouter.
func setupAIMarketSelectRouter(t *testing.T, botURL string) (*gin.Engine, string) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	t.Setenv("ENCRYPTION_KEY", "ai-market-select-test-encryption-key!")
	const jwtSecret = "ai-market-select-secret"
	// The middleware resolves its signing secret from these variables before
	// the config; pinning them keeps the token below verifiable and restores
	// the process env afterwards.
	t.Setenv("JWT_SECRET_KEY", jwtSecret)
	t.Setenv("SECRET_KEY", jwtSecret)
	middleware.InitAuthMiddleware(&config.Config{
		Auth: config.AuthSettings{
			JWTSecretKey:             jwtSecret,
			JWTAlgorithm:             "HS256",
			AccessTokenExpireMinutes: 30,
			RefreshTokenExpireDays:   7,
		},
	})

	dbConn, err := sql.Open("sqlite", "file:ai-market-select-route-test?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { _ = dbConn.Close() })
	if _, err := dbConn.Exec(`
		CREATE TABLE IF NOT EXISTS external_api_credentials (
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

	manager := auth.NewManager(auth.JWTConfig{Secret: jwtSecret, ExpiryHours: 1, RefreshExpiryDays: 7})
	userToken, _, err := manager.CreateAccessToken(1, "ai-user", "ai@example.local", false)
	if err != nil {
		t.Fatalf("create access token: %v", err)
	}

	router := gin.New()
	// An explicit bot token: with an empty one the client loads the structured
	// env profile into the process environment (JWT secrets included), which
	// would leak into every later test of the package.
	RegisterAIMarketRoutes(router, &backenddb.Database{DB: dbConn}, services.NewBotAPIClient(botURL, "ai-market-select-bot-token"))
	return router, userToken
}

// marketSelectBotStub answers the perpetual-markets route: five mainnet
// markets with statistics for purpose=backtest, four (no AAVE) for the
// runtime list.
func marketSelectBotStub(t *testing.T) *httptest.Server {
	t.Helper()
	row := func(ticker string, volume, oiUSD float64, trades int, price float64) map[string]interface{} {
		return map[string]interface{}{
			"ticker": ticker, "status": "ACTIVE", "volume_24h": volume, "open_interest": oiUSD / price,
			"open_interest_usd": oiUSD, "next_funding_rate": 0.0000125, "oracle_price": price, "trades_24h": trades,
			"price_change_24h": nil,
		}
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/markets/perpetuals" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		details := []map[string]interface{}{
			row("BTC-USD", 2.5e9, 1.2e9, 300000, 84350),
			row("ETH-USD", 1.1e9, 6e8, 200000, 3200),
			row("SOL-USD", 4e8, 2e8, 90000, 150),
			row("AAVE-USD", 5e7, 2e7, 4000, 300),
			row("ZRO-USD", 5e5, 1e6, 300, 3),
		}
		if r.URL.Query().Get("purpose") != "backtest" {
			details = append(details[:3], details[4])
		}
		names := make([]string, 0, len(details))
		for _, item := range details {
			names = append(names, item["ticker"].(string))
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"success": true,
			"message": "Retrieved perpetual markets",
			"data": map[string]interface{}{
				"markets": names, "market_details": details, "count": len(details), "source": "dydx",
				"include_settled": false, "active_total": len(details), "inactive_total": 0,
			},
		})
	}))
	t.Cleanup(server.Close)
	return server
}

func TestAIMarketRoutes_SelectGroundsTheRankingInBotMarketData(t *testing.T) {
	bot := marketSelectBotStub(t)

	var mu sync.Mutex
	var prompt string
	xai := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload struct {
			Input []struct {
				Role    string `json:"role"`
				Content string `json:"content"`
			} `json:"input"`
		}
		_ = json.Unmarshal(body, &payload)
		mu.Lock()
		if len(payload.Input) > 0 {
			prompt = payload.Input[len(payload.Input)-1].Content
		}
		mu.Unlock()
		reply, _ := json.Marshal(`{"selected_markets":["BTC-USD","ETH-USD","AAVE-USD","BTC-USD"],"pairs":[{"market_1":"BTC-USD","market_2":"ETH-USD","reason":"top two by 24 h volume and open interest"}],"rationale":"BTC-USD and ETH-USD lead on 24 h volume and open interest in the table.","confidence":0.8}`)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"resp_1","object":"response","status":"completed","model":"grok-4.3","output":[{"type":"message","role":"assistant","status":"completed","content":[{"type":"output_text","text":` + string(reply) + `}]}],"usage":{"input_tokens":900,"output_tokens":80}}`))
	}))
	t.Cleanup(xai.Close)
	t.Setenv("XAI_API_KEY", "test-xai-key")
	t.Setenv("XAI_BASE_URL", xai.URL)
	t.Setenv("XAI_MODEL", "")
	t.Setenv("XAI_REASONING_EFFORT", "")
	t.Setenv("AI_PROVIDER_GROK_ENABLED", "")

	router, token := setupAIMarketSelectRouter(t, bot.URL)
	body := bytes.NewBufferString(`{"provider":"grok","mode":"ai_recommended","limit":3,"strategy":"cointegration pairs on liquid majors","markets":["BTC-USD","ETH-USD","SOL-USD","AAVE-USD","ZRO-USD"]}`)
	request := httptest.NewRequest(http.MethodPost, "/api/v1/ai/market-filters/select", body)
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", response.Code, response.Body.String())
	}
	t.Logf("select response: %s", response.Body.String())

	var envelope struct {
		Success bool `json:"success"`
		Data    struct {
			Provider        string   `json:"provider"`
			Source          string   `json:"source"`
			SelectedMarkets []string `json:"selected_markets"`
			UsedAI          bool     `json:"used_ai"`
			Confidence      float64  `json:"confidence"`
			Basis           struct {
				UniverseCount       int      `json:"universe_count"`
				RankedCount         int      `json:"ranked_count"`
				Network             string   `json:"network"`
				Source              string   `json:"source"`
				CriteriaUsed        []string `json:"criteria_used"`
				CriteriaUnavailable []string `json:"criteria_unavailable"`
			} `json:"basis"`
			Pairs []struct {
				Market1 string `json:"market_1"`
				Market2 string `json:"market_2"`
				Reason  string `json:"reason"`
				Source  string `json:"source"`
			} `json:"pairs"`
			MarketStats []struct {
				Ticker            string   `json:"ticker"`
				Volume24hUSD      *float64 `json:"volume_24h_usd"`
				OpenInterestUSD   *float64 `json:"open_interest_usd"`
				Trades24h         *int     `json:"trades_24h"`
				FundingRate       *float64 `json:"funding_rate"`
				OraclePrice       *float64 `json:"oracle_price"`
				PriceChange24hPct *float64 `json:"price_change_24h_pct"`
				Score             float64  `json:"score"`
			} `json:"market_stats"`
			DroppedCount int `json:"dropped_count"`
		} `json:"data"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	data := envelope.Data
	if !envelope.Success || data.Provider != "grok" || data.Source != "ai" || !data.UsedAI || data.Confidence != 0.8 {
		t.Fatalf("unexpected envelope %+v", data)
	}
	if strings.Join(data.SelectedMarkets, ",") != "BTC-USD,ETH-USD" || data.DroppedCount != 2 {
		t.Fatalf("expected AAVE (not in the runtime list) and the duplicate dropped, got %v dropped=%d", data.SelectedMarkets, data.DroppedCount)
	}
	if data.Basis.UniverseCount != 4 || data.Basis.RankedCount != 4 || data.Basis.Network != "mainnet" || data.Basis.Source != "dydx" {
		t.Fatalf("unexpected basis %+v", data.Basis)
	}
	if strings.Join(data.Basis.CriteriaUsed, ",") != "volume,liquidity,tradeability,risk" || strings.Join(data.Basis.CriteriaUnavailable, ",") != "momentum,volatility,cointegration" {
		t.Fatalf("unexpected criteria %+v", data.Basis)
	}
	if len(data.Pairs) != 1 || data.Pairs[0].Market1 != "BTC-USD" || data.Pairs[0].Market2 != "ETH-USD" || data.Pairs[0].Source != "model" {
		t.Fatalf("unexpected pairs %+v", data.Pairs)
	}
	if len(data.MarketStats) != 2 || data.MarketStats[0].Ticker != "BTC-USD" || data.MarketStats[0].Volume24hUSD == nil || *data.MarketStats[0].Volume24hUSD != 2.5e9 ||
		data.MarketStats[0].Trades24h == nil || *data.MarketStats[0].Trades24h != 300000 || data.MarketStats[0].PriceChange24hPct != nil || data.MarketStats[0].Score <= data.MarketStats[1].Score {
		t.Fatalf("unexpected statistics rows %+v", data.MarketStats)
	}

	mu.Lock()
	defer mu.Unlock()
	if !strings.Contains(prompt, "1 | BTC-USD | 2500000000 | 1200000000 | 300000 | 0.0000125 | 84350 | ") || !strings.Contains(prompt, "4 of 4 eligible markets are shown") {
		t.Fatalf("expected the numeric table in the prompt, got:\n%s", prompt)
	}
	if strings.Contains(prompt, "AAVE-USD") {
		t.Fatalf("expected a market outside the runtime list to stay out of the prompt, got:\n%s", prompt)
	}
}

func TestAIMarketRoutes_SelectFailsClosedWhenTheBotIsDown(t *testing.T) {
	closed := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	closed.Close()
	t.Setenv("XAI_API_KEY", "test-xai-key")

	router, token := setupAIMarketSelectRouter(t, closed.URL)
	request := httptest.NewRequest(http.MethodPost, "/api/v1/ai/market-filters/select", bytes.NewBufferString(`{"provider":"grok","limit":3}`))
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != http.StatusBadGateway && response.Code != http.StatusGatewayTimeout {
		t.Fatalf("expected 502 or 504 without market statistics, got %d body=%s", response.Code, response.Body.String())
	}
	if strings.Contains(response.Body.String(), closed.URL) {
		t.Fatalf("expected no upstream address in the error, got %s", response.Body.String())
	}
}

// Kept apart from the test above: that helper pins the JWT secret env for its
// own token, which would not verify the token of the shared helper used here.
func TestAIMarketRoutes_SelectWithoutBotClientIsUnavailable(t *testing.T) {
	router, token, _ := setupAIMarketRouter(t)
	request := httptest.NewRequest(http.MethodPost, "/api/v1/ai/market-filters/select", bytes.NewBufferString(`{"provider":"grok","limit":3}`))
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503 without a bot client, got %d body=%s", response.Code, response.Body.String())
	}
}
