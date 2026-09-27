package handlers

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
	"github.com/dydx-trading-bot/backend-go/internal/services"
	"github.com/gin-gonic/gin"
	_ "modernc.org/sqlite"
)

// pinAnalysisProviderEnv makes every provider "not configured": the key
// resolution falls through to the process environment, so a developer's real
// key must never reach these tests.
func pinAnalysisProviderEnv(t *testing.T) {
	t.Helper()
	for _, key := range []string{
		"XAI_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY",
		"AI_PROVIDER_GROK_ENABLED", "AI_PROVIDER_OPENAI_ENABLED", "AI_PROVIDER_DEEPSEEK_ENABLED", "AI_PROVIDER_CLAUDE_ENABLED",
	} {
		t.Setenv(key, "")
	}
}

// analysisTestUniverse is the two-market universe the select route hands the
// handler in these tests.
func analysisTestUniverse() *services.MarketUniverse {
	return &services.MarketUniverse{
		Stats:   []services.MarketStat{{Ticker: "BTC-USD"}, {Ticker: "ETH-USD"}},
		Network: "mainnet",
		Source:  "test",
	}
}

// analysisRouterFor registers the analysis endpoints of one handler as user
// 7 (not an admin).
func analysisRouterFor(t *testing.T, service *services.AIMarketService) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)
	pinAnalysisProviderEnv(t)
	handler := NewAIMarketHandler(service)
	router := gin.New()
	router.Use(func(c *gin.Context) {
		c.Set("user_id", 7)
		c.Set("is_admin", false)
		c.Next()
	})
	router.POST("/suggest", handler.SuggestStrategyParams)
	router.POST("/explain", handler.ExplainBacktest)
	router.POST("/select", func(c *gin.Context) { handler.SelectMarkets(c, analysisTestUniverse()) })
	return router
}

// analysisTestRouter is the unwired service: no strategy or backtest store.
func analysisTestRouter(t *testing.T) *gin.Engine {
	t.Helper()
	return analysisRouterFor(t, services.NewAIMarketService(nil))
}

var analysisTestDBCount atomic.Int64

// wiredAnalysisFixture is a service over a sqlite strategy and backtest
// mirror: user 7 owns one strategy, one completed run and one running run;
// user 8 owns a strategy and a run of their own. No provider key exists.
type wiredAnalysisFixture struct {
	router                         *gin.Engine
	ownedStrategy, foreignStrategy int
	ownedRun, foreignRun           string
	runningRun                     string
}

func newWiredAnalysisFixture(t *testing.T) *wiredAnalysisFixture {
	t.Helper()
	t.Setenv("DB_TYPE", "sqlite")
	conn, err := sql.Open("sqlite", fmt.Sprintf("file:ai-analysis-handler-%d?mode=memory&cache=shared", analysisTestDBCount.Add(1)))
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	conn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = conn.Close() })
	for _, statement := range []string{
		`CREATE TABLE backtest_strategies (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			name TEXT NOT NULL,
			description TEXT,
			category TEXT,
			is_public BOOLEAN NOT NULL DEFAULT 0,
			is_default BOOLEAN NOT NULL DEFAULT 0,
			runtime_strategy TEXT NOT NULL DEFAULT 'cointegration',
			runtime_network TEXT NOT NULL DEFAULT 'testnet',
			runtime_subaccount INTEGER NOT NULL DEFAULT 0,
			pair_selection_mode TEXT NOT NULL DEFAULT 'liquidity',
			selected_markets TEXT NOT NULL DEFAULT '[]',
			zscore_threshold REAL NOT NULL,
			stats_window INTEGER NOT NULL,
			max_half_life REAL NOT NULL,
			usd_per_trade REAL NOT NULL,
			usd_min_collateral REAL NOT NULL,
			close_at_zscore_cross BOOLEAN NOT NULL,
			find_cointegrated_pairs BOOLEAN NOT NULL,
			manage_exits BOOLEAN NOT NULL,
			place_trades BOOLEAN NOT NULL,
			abort_all_positions BOOLEAN NOT NULL,
			max_positions INTEGER NOT NULL,
			max_drawdown_pct REAL NOT NULL,
			stop_loss_pct REAL NOT NULL,
			take_profit_pct REAL NOT NULL,
			trailing_stop_pct REAL NOT NULL,
			rebalance_interval_hours INTEGER NOT NULL,
			position_timeout_hours INTEGER NOT NULL,
			transaction_fee REAL NOT NULL,
			slippage REAL NOT NULL,
			starting_balance REAL NOT NULL,
			candle_resolution TEXT NOT NULL,
			max_history_days INTEGER NOT NULL,
			benchmark_symbol TEXT NOT NULL,
			risk_free_rate REAL NOT NULL,
			initial_amount REAL NOT NULL,
			usage_count INTEGER NOT NULL DEFAULT 0,
			last_used_at DATETIME,
			deleted_at DATETIME,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL
		)`,
		`CREATE TABLE backtest_runs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER,
			strategy_id INTEGER,
			strategy_version_id INTEGER,
			run_id TEXT NOT NULL,
			status TEXT,
			start_date TEXT NOT NULL DEFAULT '',
			end_date TEXT NOT NULL DEFAULT '',
			num_pairs INTEGER NOT NULL DEFAULT 0,
			total_markets INTEGER NOT NULL DEFAULT 0,
			resolution TEXT,
			total_trades INTEGER,
			profitable_trades INTEGER,
			losing_trades INTEGER,
			win_rate REAL,
			total_pnl REAL,
			total_pnl_usd REAL,
			sharpe_ratio REAL,
			sortino_ratio REAL,
			calmar_ratio REAL,
			max_drawdown REAL,
			profit_factor REAL,
			starting_balance REAL,
			ending_balance REAL,
			max_balance REAL,
			min_balance REAL,
			error_message TEXT,
			started_at DATETIME,
			completed_at DATETIME,
			duration_seconds REAL,
			config TEXT,
			created_at DATETIME NOT NULL
		)`,
	} {
		if _, err := conn.Exec(statement); err != nil {
			t.Fatalf("create schema: %v", err)
		}
	}

	strategies := services.NewStrategyService(repository.NewStrategyRepository(conn))
	owned, err := strategies.CreateStrategy(7, "Owned majors", "", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create owned strategy: %v", err)
	}
	foreign, err := strategies.CreateStrategy(8, "Foreign majors", "", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create foreign strategy: %v", err)
	}
	f := &wiredAnalysisFixture{
		ownedStrategy: owned.ID, foreignStrategy: foreign.ID,
		ownedRun: "run-owned-0001", foreignRun: "run-foreign-0002", runningRun: "run-owned-0003",
	}
	for _, run := range []struct {
		user       int
		strategy   int
		id, status string
	}{
		{7, owned.ID, f.ownedRun, "completed"},
		{8, foreign.ID, f.foreignRun, "completed"},
		{7, owned.ID, f.runningRun, "running"},
	} {
		if _, err := conn.Exec(`INSERT INTO backtest_runs (user_id, strategy_id, run_id, status, created_at) VALUES (?, ?, ?, ?, ?)`,
			run.user, run.strategy, run.id, run.status, time.Now().UTC()); err != nil {
			t.Fatalf("insert run %s: %v", run.id, err)
		}
	}

	backtests := repository.NewBacktestRepository(conn)
	service := services.NewAIMarketService(nil)
	service.SetStrategyEvidence(services.NewStrategyEvidenceBuilder(backtests, nil), strategies, backtests)
	f.router = analysisRouterFor(t, service)
	return f
}

func postAnalysis(router *gin.Engine, path string, body string) (int, map[string]any) {
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	res := httptest.NewRecorder()
	router.ServeHTTP(res, req)
	var envelope map[string]any
	_ = json.Unmarshal(res.Body.Bytes(), &envelope)
	return res.Code, envelope
}

func analysisErrorText(envelope map[string]any) string {
	message, _ := envelope["error"].(string)
	return message
}

func TestAnalysisHandlersValidateInputBeforeAnyBudget(t *testing.T) {
	router := analysisTestRouter(t)
	status, envelope := postAnalysis(router, "/suggest", `{"provider":"grok"}`)
	if status != http.StatusBadRequest || envelope["error"] != "strategy_id is required" || envelope["success"] != false {
		t.Fatalf("expected 400 without strategy_id, got %d %+v", status, envelope)
	}
	status, envelope = postAnalysis(router, "/explain", `{"provider":"grok"}`)
	if status != http.StatusBadRequest || envelope["error"] != "run_id is required" {
		t.Fatalf("expected 400 without run_id, got %d %+v", status, envelope)
	}
	status, _ = postAnalysis(router, "/suggest", `{bad json`)
	if status != http.StatusBadRequest {
		t.Fatalf("expected 400 for a bad body, got %d", status)
	}
	status, _ = postAnalysis(router, "/select", `{bad json`)
	if status != http.StatusBadRequest {
		t.Fatalf("expected 400 for a bad select body, got %d", status)
	}

	// A typed request error maps onto its own status: the unwired service
	// answers 503, and the timestamp envelope is kept.
	status, envelope = postAnalysis(router, "/suggest", `{"strategy_id":1}`)
	if status != http.StatusServiceUnavailable || envelope["error"] != "Strategy evidence is not configured" {
		t.Fatalf("expected the typed 503, got %d %+v", status, envelope)
	}
	if _, ok := envelope["timestamp"].(string); !ok {
		t.Fatalf("expected the APIResponse envelope, got %+v", envelope)
	}
	status, envelope = postAnalysis(router, "/explain", `{"run_id":"run-1"}`)
	if status != http.StatusServiceUnavailable || envelope["error"] != "Backtest evidence is not configured" {
		t.Fatalf("expected the typed 503, got %d %+v", status, envelope)
	}
}

// TestAnalysisHandlersShareTheChatBudget: suggestions, explanations and
// market selection draw on one per-user budget (burst of 3, then 429 with
// the chat's codes). Without a provider key each accepted request ends in
// the provider's 409, which is reached only after the budget was taken.
func TestAnalysisHandlersShareTheChatBudget(t *testing.T) {
	f := newWiredAnalysisFixture(t)
	explain := fmt.Sprintf(`{"run_id":%q}`, f.ownedRun)
	statuses := make([]int, 0, 4)
	for i := 0; i < 4; i++ {
		status, envelope := postAnalysis(f.router, "/explain", explain)
		statuses = append(statuses, status)
		switch status {
		case http.StatusConflict:
			if !strings.Contains(analysisErrorText(envelope), "not configured with active credentials") {
				t.Fatalf("expected the provider's not-configured message, got %+v", envelope)
			}
		case http.StatusTooManyRequests:
			if !strings.HasPrefix(analysisErrorText(envelope), services.StrategyChatCodeRateLimited+":") {
				t.Fatalf("expected the chat's rate-limit code in the error text, got %+v", envelope)
			}
		}
	}
	if statuses[0] != http.StatusConflict || statuses[1] != http.StatusConflict || statuses[2] != http.StatusConflict || statuses[3] != http.StatusTooManyRequests {
		t.Fatalf("expected three attempts then a rate limit, got %v", statuses)
	}
	status, envelope := postAnalysis(f.router, "/select", `{"provider":"grok","limit":2}`)
	if status != http.StatusTooManyRequests || !strings.HasPrefix(analysisErrorText(envelope), services.StrategyChatCodeRateLimited+":") {
		t.Fatalf("expected market selection to share the budget, got %d %+v", status, envelope)
	}
	status, envelope = postAnalysis(f.router, "/suggest", fmt.Sprintf(`{"strategy_id":%d}`, f.ownedStrategy))
	if status != http.StatusTooManyRequests || !strings.HasPrefix(analysisErrorText(envelope), services.StrategyChatCodeRateLimited+":") {
		t.Fatalf("expected suggest-params to share the budget, got %d %+v", status, envelope)
	}
}

// TestMarketSelectionTakesTheAnalysisBudget: select is limited on its own
// too, with the same codes.
func TestMarketSelectionTakesTheAnalysisBudget(t *testing.T) {
	router := analysisTestRouter(t)
	statuses := make([]int, 0, 4)
	for i := 0; i < 4; i++ {
		status, envelope := postAnalysis(router, "/select", `{"provider":"grok","limit":2}`)
		statuses = append(statuses, status)
		if status == http.StatusConflict && !strings.Contains(analysisErrorText(envelope), "Grok is not configured") {
			t.Fatalf("expected the provider's not-configured message, got %+v", envelope)
		}
		if status == http.StatusTooManyRequests && !strings.HasPrefix(analysisErrorText(envelope), services.StrategyChatCodeRateLimited+":") {
			t.Fatalf("expected the chat's rate-limit code, got %+v", envelope)
		}
	}
	if statuses[0] != http.StatusConflict || statuses[1] != http.StatusConflict || statuses[2] != http.StatusConflict || statuses[3] != http.StatusTooManyRequests {
		t.Fatalf("expected three attempts then a rate limit, got %v", statuses)
	}
}

// TestAnalysisHandlersAuthorizeBeforeSpendingBudget: a strategy or run that
// is not the caller's, or a run that has not completed, is refused without
// taking a token; the refusal is the same once the budget is gone.
func TestAnalysisHandlersAuthorizeBeforeSpendingBudget(t *testing.T) {
	f := newWiredAnalysisFixture(t)
	foreignSuggest := fmt.Sprintf(`{"strategy_id":%d}`, f.foreignStrategy)
	foreignExplain := fmt.Sprintf(`{"run_id":%q}`, f.foreignRun)
	runningExplain := fmt.Sprintf(`{"run_id":%q}`, f.runningRun)
	for i := 0; i < 4; i++ {
		if status, envelope := postAnalysis(f.router, "/suggest", foreignSuggest); status != http.StatusNotFound || envelope["error"] != "Strategy not found" {
			t.Fatalf("expected 404 for a foreign strategy, got %d %+v", status, envelope)
		}
		if status, envelope := postAnalysis(f.router, "/explain", foreignExplain); status != http.StatusNotFound || envelope["error"] != "Backtest run not found" {
			t.Fatalf("expected 404 for a foreign run, got %d %+v", status, envelope)
		}
		if status, envelope := postAnalysis(f.router, "/explain", runningExplain); status != http.StatusConflict || envelope["error"] != "The backtest has not completed yet" {
			t.Fatalf("expected 409 for a run that has not completed, got %d %+v", status, envelope)
		}
	}

	// Twelve refusals later the whole burst is still available.
	ownedExplain := fmt.Sprintf(`{"run_id":%q}`, f.ownedRun)
	for i := 0; i < 3; i++ {
		if status, envelope := postAnalysis(f.router, "/explain", ownedExplain); status != http.StatusConflict || !strings.Contains(analysisErrorText(envelope), "not configured with active credentials") {
			t.Fatalf("expected attempt %d on the owner's run to reach the provider check, got %d %+v", i+1, status, envelope)
		}
	}
	if status, _ := postAnalysis(f.router, "/explain", ownedExplain); status != http.StatusTooManyRequests {
		t.Fatalf("expected the budget exhausted, got %d", status)
	}
	// Refusals stay refusals, not rate limits.
	if status, _ := postAnalysis(f.router, "/suggest", foreignSuggest); status != http.StatusNotFound {
		t.Fatalf("expected 404 before the rate limit, got %d", status)
	}
	if status, _ := postAnalysis(f.router, "/explain", foreignExplain); status != http.StatusNotFound {
		t.Fatalf("expected 404 before the rate limit, got %d", status)
	}
	if status, _ := postAnalysis(f.router, "/explain", runningExplain); status != http.StatusConflict {
		t.Fatalf("expected 409 before the rate limit, got %d", status)
	}
}

func TestAnalysisHandlerDeadlines(t *testing.T) {
	if aiBacktestExplainDeadline != 150*time.Second || aiSuggestParamsDeadline != 170*time.Second {
		t.Fatalf("unexpected deadlines explain=%s suggest=%s", aiBacktestExplainDeadline, aiSuggestParamsDeadline)
	}
	if aiAnalysisRequestBurst != 3 || aiAnalysisRequestsPerSecond != 6.0/60.0 {
		t.Fatalf("unexpected budget burst=%d rps=%v", aiAnalysisRequestBurst, aiAnalysisRequestsPerSecond)
	}
}
