package services

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

// fakeEvidenceBotState is shared by every copy of a fakeEvidenceBot so the
// call log survives WithRequestContext and WithToken.
type fakeEvidenceBotState struct {
	mu     sync.Mutex
	calls  []string
	tokens []string
	// stall makes every call wait for its context to end, like a hung bot.
	stall bool

	status       func(runID string) (map[string]interface{}, error)
	trades       func(runID string, limit, offset int) (map[string]interface{}, error)
	liveTrades   func(instanceID string, status *string, limit, offset *int) (map[string]interface{}, error)
	positions    func(instanceID string) (map[string]interface{}, error)
	stats        func(instanceID string) (map[string]interface{}, error)
	entryHalt    func(instanceID string) (map[string]interface{}, error)
	cointegrated func(instanceID string) (map[string]interface{}, error)
}

type fakeEvidenceBot struct {
	state *fakeEvidenceBotState
	ctx   context.Context
	token string
}

func newFakeEvidenceBot() *fakeEvidenceBot {
	return &fakeEvidenceBot{state: &fakeEvidenceBotState{}, ctx: context.Background()}
}

func (f *fakeEvidenceBot) record(call string) error {
	f.state.mu.Lock()
	f.state.calls = append(f.state.calls, call)
	f.state.tokens = append(f.state.tokens, f.token)
	stall := f.state.stall
	f.state.mu.Unlock()
	if stall {
		<-f.ctx.Done()
		return &BotAPITransportError{StatusCode: http.StatusGatewayTimeout, Message: "upstream bot API request timed out", Cause: f.ctx.Err()}
	}
	return nil
}

func (f *fakeEvidenceBot) callsOf(prefix string) int {
	f.state.mu.Lock()
	defer f.state.mu.Unlock()
	count := 0
	for _, call := range f.state.calls {
		if strings.HasPrefix(call, prefix) {
			count++
		}
	}
	return count
}

func notFoundBotError() error {
	return &BotAPIError{StatusCode: http.StatusNotFound, Message: "Not Found"}
}

func (f *fakeEvidenceBot) GetBacktestStatus(runID string) (map[string]interface{}, error) {
	if err := f.record("status:" + runID); err != nil {
		return nil, err
	}
	if f.state.status == nil {
		return nil, notFoundBotError()
	}
	return f.state.status(runID)
}

func (f *fakeEvidenceBot) GetBacktestTradesWithFilters(runID string, limit, offset int, winningOnly bool) (map[string]interface{}, error) {
	if err := f.record(fmt.Sprintf("trades:%s:%d:%d:%v", runID, limit, offset, winningOnly)); err != nil {
		return nil, err
	}
	if f.state.trades == nil {
		return nil, notFoundBotError()
	}
	return f.state.trades(runID, limit, offset)
}

func (f *fakeEvidenceBot) GetBotInstanceTrades(instanceID string, status *string, limit *int, offset *int) (map[string]interface{}, error) {
	if err := f.record("live-trades:" + instanceID); err != nil {
		return nil, err
	}
	if f.state.liveTrades == nil {
		return nil, notFoundBotError()
	}
	return f.state.liveTrades(instanceID, status, limit, offset)
}

func (f *fakeEvidenceBot) GetCurrentPositions(instanceID string) (map[string]interface{}, error) {
	if err := f.record("positions:" + instanceID); err != nil {
		return nil, err
	}
	if f.state.positions == nil {
		return nil, notFoundBotError()
	}
	return f.state.positions(instanceID)
}

func (f *fakeEvidenceBot) GetRealtimeStats(instanceID string) (map[string]interface{}, error) {
	if err := f.record("stats:" + instanceID); err != nil {
		return nil, err
	}
	if f.state.stats == nil {
		return nil, notFoundBotError()
	}
	return f.state.stats(instanceID)
}

func (f *fakeEvidenceBot) GetBotEntryHalt(instanceID string) (map[string]interface{}, error) {
	if err := f.record("entry-halt:" + instanceID); err != nil {
		return nil, err
	}
	if f.state.entryHalt == nil {
		return nil, notFoundBotError()
	}
	return f.state.entryHalt(instanceID)
}

func (f *fakeEvidenceBot) GetBotCointegratedPairs(instanceID string) (map[string]interface{}, error) {
	if err := f.record("cointegrated:" + instanceID); err != nil {
		return nil, err
	}
	if f.state.cointegrated == nil {
		return nil, notFoundBotError()
	}
	return f.state.cointegrated(instanceID)
}

func (f *fakeEvidenceBot) WithRequestContext(ctx context.Context) BotEvidenceClient {
	return &fakeEvidenceBot{state: f.state, ctx: ctx, token: f.token}
}

func (f *fakeEvidenceBot) WithToken(token string) BotEvidenceClient {
	return &fakeEvidenceBot{state: f.state, ctx: f.ctx, token: token}
}

// evidenceTestDBCount keeps every fixture database distinct, even inside one test.
var evidenceTestDBCount atomic.Int64

// evidenceTestDB is the chat test schema with a backtest_runs table that
// also holds the config snapshot.
func evidenceTestDB(t *testing.T) *sql.DB {
	t.Helper()
	t.Setenv("DB_TYPE", "sqlite")
	// Pin the bot token settings so the builder never auto-loads a profile
	// and forwards the caller's token deterministically.
	t.Setenv("BOT_API_TOKEN", "evidence-test-service-token")
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "false")
	conn, err := sql.Open("sqlite", fmt.Sprintf("file:evidence-%s-%d?mode=memory&cache=shared", strings.ReplaceAll(t.Name(), "/", "_"), evidenceTestDBCount.Add(1)))
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	conn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = conn.Close() })
	for _, statement := range strategyChatTestSchema {
		if strings.Contains(statement, "CREATE TABLE backtest_runs") {
			statement = strings.Replace(statement, "duration_seconds REAL,", "duration_seconds REAL,\n\t\t\tconfig TEXT,\n\t\t\tstrategy_snapshot TEXT,", 1)
		}
		if _, err := conn.Exec(statement); err != nil {
			t.Fatalf("create schema: %v", err)
		}
	}
	return conn
}

type evidenceRunRow struct {
	userID, strategyID int
	runID, status      string
	totalTrades        int
	winRate            *float64
	drawdown           *float64
	config             string
	createdAt          time.Time
}

func insertEvidenceRun(t *testing.T, conn *sql.DB, row evidenceRunRow) {
	t.Helper()
	if _, err := conn.Exec(`INSERT INTO backtest_runs (user_id, strategy_id, run_id, status, start_date, end_date, resolution, num_pairs, total_trades, win_rate, total_pnl_usd, sharpe_ratio, max_drawdown, profit_factor, config, completed_at, created_at)
		VALUES (?, ?, ?, ?, '2026-06-01', '2026-09-01', '1HOUR', 4, ?, ?, 42.5, 1.2, ?, 1.4, ?, ?, ?)`,
		row.userID, row.strategyID, row.runID, row.status, row.totalTrades, row.winRate, row.drawdown, sql.NullString{String: row.config, Valid: row.config != ""}, row.createdAt, row.createdAt); err != nil {
		t.Fatalf("insert run %s: %v", row.runID, err)
	}
}

func evidenceTestStrategy() *models.BacktestStrategy {
	strategy := chatTestStrategy()
	strategy.UserID = 4242
	strategy.ID = 101
	strategy.RuntimeSubaccount = 7
	return strategy
}

func evidenceRunningState(t *testing.T) *models.StrategyExecutionState {
	t.Helper()
	return &models.StrategyExecutionState{
		StrategyID: 101, IsRunning: true,
		State: sql.NullString{Valid: true, String: `{"instance_id":"strategy-4242-101","status":"running","bot_status":"running","network":"testnet","last_confirmed_at":"2026-09-26T10:00:00Z","last_error":"Loaded wallet for address dydx1abcdefghijklmnop at http://bot-api:8889"}`},
	}
}

func floatPtr(value float64) *float64 { return &value }

// backtestTradesPayload builds a bot trades reply: count trades spread over
// pairs, P&L alternating so every pair has wins and losses; feeNil marks
// trade indexes whose costs are missing.
func backtestTradesPayload(count int, pairs []string, feeNil map[int]bool, exitReason bool) map[string]interface{} {
	trades := make([]interface{}, 0, count)
	for i := 0; i < count; i++ {
		pair := strings.Split(pairs[i%len(pairs)], "/")
		pnl := float64((i%len(pairs))+1) * 10
		if i%3 == 2 {
			pnl = -pnl / 2
		}
		row := map[string]interface{}{
			"trade_id":       fmt.Sprintf("t-%03d", i),
			"market_1":       pair[0],
			"market_2":       pair[1],
			"pnl_usd":        pnl,
			"pnl_pct":        pnl / 100 * 100 / 250, // percent of a 250 USD trade
			"duration_hours": float64(4 + i%5),
			"entry_zscore":   2.0 + float64(i%3)/10,
			"exit_zscore":    0.1,
			"win":            pnl > 0,
			"hedge_ratio":    0.5,
		}
		if !feeNil[i] {
			row["fee_cost"] = 0.25
			row["slippage_cost"] = 0.5
		}
		if exitReason {
			row["exit_reason"] = []string{"zscore_cross", "stop_loss", "timeout"}[i%3]
		}
		trades = append(trades, row)
	}
	return map[string]interface{}{"success": true, "data": map[string]interface{}{"run_id": "run", "trades": trades, "total": count, "count": count}}
}

// liveTradesPayload is the OLD bot's reply to GET /bots/{id}/trades: every
// closed trade whatever the limit, oldest first, total_trades counting them
// all.
func liveTradesPayload(count int, pairs []string) map[string]interface{} {
	trades := make([]interface{}, 0, count)
	base := time.Date(2026, 9, 1, 0, 0, 0, 0, time.UTC)
	for i := 0; i < count; i++ {
		pair := strings.Split(pairs[i%len(pairs)], "/")
		pnl := 5.0
		if i%4 == 3 {
			pnl = -3
		}
		trades = append(trades, map[string]interface{}{
			"trade_id": fmt.Sprintf("live-%d", i), "pair1": pair[0], "pair2": pair[1], "status": "CLOSED",
			"profit_loss": pnl, "profit_loss_percentage": pnl / 2, "duration_seconds": 7200.0,
			"opened_at": base.Add(time.Duration(i) * time.Minute).Format(time.RFC3339),
			"closed_at": base.Add(time.Duration(i)*time.Minute + 2*time.Hour).Format(time.RFC3339),
		})
	}
	return map[string]interface{}{"success": true, "data": map[string]interface{}{"instance_id": "strategy-4242-101", "total_trades": count, "trades": trades}}
}

// liveTradesPage is the NEW bot's reply: the matching trades newest first,
// paged by limit and offset, with total_trades counting them before paging,
// count the trades in the page and the limit and offset echoed.
func liveTradesPage(total int, limit, offset *int, pairs []string) map[string]interface{} {
	page := liveTradesPayload(total, pairs)
	data := page["data"].(map[string]interface{})
	oldestFirst := data["trades"].([]interface{})
	trades := make([]interface{}, 0, len(oldestFirst))
	for i := len(oldestFirst) - 1; i >= 0; i-- {
		trades = append(trades, oldestFirst[i])
	}
	start := 0
	if offset != nil && *offset > 0 {
		start = min(*offset, len(trades))
	}
	end := len(trades)
	if limit != nil && *limit > 0 && start+*limit < end {
		end = start + *limit
	}
	data["trades"] = trades[start:end]
	data["count"] = end - start
	data["offset"] = start
	data["limit"] = nil
	if limit != nil && *limit > 0 {
		data["limit"] = *limit
	}
	return page
}

func positionsPayload(count int, pairs []string) map[string]interface{} {
	positions := make([]interface{}, 0, count)
	for i := 0; i < count; i++ {
		pair := strings.Split(pairs[i%len(pairs)], "/")
		positions = append(positions, map[string]interface{}{
			"position_id": fmt.Sprintf("pos-%d", i), "pair1": pair[0], "pair2": pair[1], "status": "OPEN",
			"unrealized_pnl": float64(i) - 2, "unrealized_pnl_pct": 0.5, "z_score_entry": 2.1, "z_score_current": 1.4,
			"entered_at": "2026-09-26T08:00:00+00:00", "entry_price1": 1.0, "current_size1": 3.0,
		})
	}
	return map[string]interface{}{"success": true, "data": map[string]interface{}{"bot_instance_id": "strategy-4242-101", "positions": positions, "count": count}}
}

func evidencePairs(count int) []string {
	pairs := make([]string, 0, count)
	for i := 0; i < count; i++ {
		pairs = append(pairs, fmt.Sprintf("A%02d-USD/B%02d-USD", i, i))
	}
	return pairs
}

func newEvidenceBuilder(t *testing.T, conn *sql.DB, bot *fakeEvidenceBot) *StrategyEvidenceBuilder {
	t.Helper()
	var client BotEvidenceClient
	if bot != nil {
		client = bot
	}
	builder := NewStrategyEvidenceBuilder(repository.NewBacktestRepository(conn), client)
	builder.now = func() time.Time { return time.Date(2026, 9, 26, 12, 0, 0, 0, time.UTC) }
	return builder
}

func evidenceNotesContain(evidence *StrategyEvidence, note string) bool {
	for _, item := range evidence.DataNotes {
		if item == note {
			return true
		}
	}
	return false
}

func TestEvidenceNoRunsAndNeverStarted(t *testing.T) {
	conn := evidenceTestDB(t)
	bot := newFakeEvidenceBot()
	builder := newEvidenceBuilder(t, conn, bot)

	evidence := builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions())
	if !evidenceNotesContain(evidence, evidenceNoteNoRuns) || !evidenceNotesContain(evidence, evidenceNoteNeverStarted) {
		t.Fatalf("expected the no-runs and never-started notes, got %v", evidence.DataNotes)
	}
	if evidence.Live != nil || evidence.Backtests.LatestRun != nil || len(evidence.Backtests.CompletedRuns) != 0 || evidence.Cointegration != nil {
		t.Fatalf("expected an empty evidence, got %+v", evidence)
	}
	if len(bot.state.calls) != 0 {
		t.Fatalf("expected no bot calls without runs or runtime, got %v", bot.state.calls)
	}
	summary := evidence.Summary
	if summary.CompletedRuns != 0 || summary.LiveAvailable || summary.CointegratedPairs != 0 || len(summary.DataNotes) != len(evidence.DataNotes) {
		t.Fatalf("unexpected summary %+v", summary)
	}

	// A builder without a repository still answers, with a note.
	orphan := NewStrategyEvidenceBuilder(nil, nil)
	if got := orphan.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions()); !evidenceNotesContain(got, evidenceNoteRunsUnavailable) {
		t.Fatalf("expected the history-unavailable note, got %v", got.DataNotes)
	}
}

func TestEvidenceLedgerMissingWhenBotAnswers404(t *testing.T) {
	conn := evidenceTestDB(t)
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 4242, strategyID: 101, runID: "run-aaaa-1111", status: "completed", totalTrades: 25, winRate: floatPtr(0.55), drawdown: floatPtr(12.5), createdAt: time.Now().UTC()})
	bot := newFakeEvidenceBot() // no trades handler: 404
	builder := newEvidenceBuilder(t, conn, bot)

	evidence := builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions())
	if len(evidence.Backtests.CompletedRuns) != 1 || evidence.Backtests.LatestRun != nil {
		t.Fatalf("expected one run without a ledger, got %+v", evidence.Backtests)
	}
	if !evidenceNotesContain(evidence, evidenceNoteLedgerMissing) {
		t.Fatalf("expected the ledger-missing note, got %v", evidence.DataNotes)
	}
	run := evidence.Backtests.CompletedRuns[0]
	if run.RunRef != "run-aaaa" || run.WinRatePct == nil || *run.WinRatePct != 55 || run.MaxDrawdownPct == nil || *run.MaxDrawdownPct != 12.5 || run.ProfitFactor == nil || *run.ProfitFactor != 1.4 {
		t.Fatalf("expected mirror units normalized once (0.55 -> 55, drawdown as-is), got %+v", run)
	}
	// A failed ledger fetch is not cached: the next build asks again.
	builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions())
	if got := bot.callsOf("trades:"); got != 2 {
		t.Fatalf("expected the failed fetch to be retried on the next build, got %d trade calls", got)
	}
}

func TestEvidenceLedgerAggregatesPairsAndFoldsTheRest(t *testing.T) {
	conn := evidenceTestDB(t)
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 4242, strategyID: 101, runID: "run-bbbb-2222", status: "completed", totalTrades: 25, winRate: floatPtr(55), drawdown: floatPtr(12.5),
		config: `{"trading_parameters":{"zscore_threshold":2.0,"stats_window":50,"resolution":"1HOUR","max_drawdown_pct":10,"runtime_subaccount":3,"selected_markets":["BTC-USD"]}}`, createdAt: time.Now().UTC()})
	pairs := []string{"BTC-USD/ETH-USD", "SOL-USD/AVAX-USD", "LINK-USD/DOT-USD", "ATOM-USD/NEAR-USD"}
	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		if limit != 2000 || offset != 0 {
			t.Fatalf("expected the fixed 2000-trade page, got limit=%d offset=%d", limit, offset)
		}
		return backtestTradesPayload(25, pairs, map[int]bool{3: true, 7: true}, true), nil
	}
	bot.state.status = func(runID string) (map[string]interface{}, error) {
		return map[string]interface{}{"success": true, "data": map[string]interface{}{
			"run_id": runID, "status": "completed",
			"request":  map[string]interface{}{"runtime_subaccount": 7, "metadata": map[string]interface{}{"owner": "dydx1abcdefghijklmnop"}},
			"metadata": map[string]interface{}{"drawdown_halt": map[string]interface{}{"limit_pct": 10.0, "reached": true, "trades_skipped": 3, "reached_at": "2026-08-01T00:00:00Z"}, "market_data_network": "mainnet"},
		}}, nil
	}
	builder := newEvidenceBuilder(t, conn, bot)

	evidence := builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, EvidenceOptions{Pairs: 2})
	ledger := evidence.Backtests.LatestRun
	if ledger == nil {
		t.Fatalf("expected a ledger, notes %v", evidence.DataNotes)
	}
	if ledger.TradesAnalysed != 25 || ledger.TradesTotal != 25 || ledger.Truncated || ledger.CostsKnown || ledger.FeesUSD != nil {
		t.Fatalf("expected 25 analysed trades with unknown costs, got %+v", ledger)
	}
	if !evidenceNotesContain(evidence, evidenceNoteCostsUnknown) {
		t.Fatalf("expected the costs-unknown note, got %v", evidence.DataNotes)
	}
	if len(ledger.Pairs) != 2 || ledger.PairsOmitted != 2 || ledger.Other == nil || ledger.Other.Pair != "other" {
		t.Fatalf("expected two pairs kept and two folded, got pairs=%+v omitted=%d other=%+v", ledger.Pairs, ledger.PairsOmitted, ledger.Other)
	}
	if ledger.Pairs[0].Pair != "ATOM-USD/NEAR-USD" || ledger.Pairs[1].Pair != "LINK-USD/DOT-USD" {
		t.Fatalf("expected pairs ordered by |pnl| desc, got %+v", ledger.Pairs)
	}
	top := ledger.Pairs[0]
	if top.Trades != 6 || top.Wins != 4 || top.WinRatePct != 66.67 || top.MaxLossUSD != -20 || top.MaxWinUSD != 40 || top.ExitReasons["timeout"] == 0 {
		t.Fatalf("unexpected top pair aggregate %+v", top)
	}
	// The two cost-less trades both belong to the top pair, so its fees are
	// unknown while the folded remainder still sums its known costs.
	if top.FeesUSD != nil || ledger.Other.Trades != 13 || ledger.Other.FeesUSD == nil || *ledger.Other.FeesUSD != 9.75 {
		t.Fatalf("unexpected fee handling: top=%+v other=%+v", top, ledger.Other)
	}
	if ledger.DrawdownHalt == nil || !ledger.DrawdownHalt.Reached || ledger.DrawdownHalt.TradesSkipped != 3 || ledger.DrawdownHalt.LimitPct != 10 || ledger.MarketDataNetwork != "mainnet" {
		t.Fatalf("expected the drawdown halt and network from the status, got %+v", ledger)
	}
	if ledger.ExitReasons["zscore_cross"]+ledger.ExitReasons["stop_loss"]+ledger.ExitReasons["timeout"] != 25 || ledger.AvgAbsEntryZScore < 2 {
		t.Fatalf("unexpected ledger totals %+v", ledger)
	}
	settings := evidence.Backtests.CompletedRuns[0].Settings
	if settings["zscore_threshold"] != 2.0 || settings["stats_window"] != 50 || settings["candle_resolution"] != "1HOUR" || settings["max_drawdown_pct"] != 10.0 {
		t.Fatalf("expected allowlisted settings from the config snapshot, got %+v", settings)
	}
	if _, leaked := settings["runtime_subaccount"]; leaked {
		t.Fatalf("runtime_subaccount must not be copied from the snapshot: %+v", settings)
	}
	if _, leaked := settings["selected_markets"]; leaked {
		t.Fatalf("selected_markets must not be copied from the snapshot: %+v", settings)
	}
	if evidence.Summary.TradesAnalysed != 25 || evidence.Summary.PairsAnalysed != 4 || evidence.Summary.CompletedRuns != 1 {
		t.Fatalf("unexpected summary %+v", evidence.Summary)
	}

	// The same run again: the ledger comes from the cache, no bot call.
	before := len(bot.state.calls)
	again := builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, EvidenceOptions{Pairs: 4})
	if len(bot.state.calls) != before {
		t.Fatalf("expected the cached ledger, got new bot calls %v", bot.state.calls[before:])
	}
	if len(again.Backtests.LatestRun.Pairs) != 4 || again.Backtests.LatestRun.Other != nil || len(ledger.Pairs) != 2 {
		t.Fatalf("expected the cached full ledger folded per call without touching earlier results, got %+v", again.Backtests.LatestRun)
	}
	if builder.runs.size() != 1 {
		t.Fatalf("expected one cached ledger, got %d", builder.runs.size())
	}
}

func TestEvidenceLedgerTruncationFlagAndOldBotWithoutExitReason(t *testing.T) {
	conn := evidenceTestDB(t)
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 4242, strategyID: 101, runID: "run-cccc-3333", status: "completed", totalTrades: 3000, winRate: floatPtr(0.5), drawdown: floatPtr(3), createdAt: time.Now().UTC()})
	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		return backtestTradesPayload(limit, evidencePairs(3), nil, false), nil
	}
	builder := newEvidenceBuilder(t, conn, bot)

	evidence := builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions())
	ledger := evidence.Backtests.LatestRun
	if ledger == nil || !ledger.Truncated || ledger.TradesAnalysed != 2000 || ledger.TradesTotal != 3000 || !ledger.CostsKnown {
		t.Fatalf("expected a truncated ledger with known costs, got %+v", ledger)
	}
	if !evidenceNotesContain(evidence, "Only the first 2000 of 3000 trades were analysed.") {
		t.Fatalf("expected the truncation note, got %v", evidence.DataNotes)
	}
	if ledger.ExitReasons != nil || ledger.Pairs[0].ExitReasons != nil {
		t.Fatalf("expected no exit reasons from an old bot, got %+v", ledger)
	}
	if ledger.FeesUSD == nil || *ledger.FeesUSD != 500 || ledger.SlippageUSD == nil || *ledger.SlippageUSD != 1000 {
		t.Fatalf("expected summed fee and slippage costs, got fees=%v slippage=%v", ledger.FeesUSD, ledger.SlippageUSD)
	}
}

func TestEvidenceLiveBlockUnitsCapsAndAllowlist(t *testing.T) {
	conn := evidenceTestDB(t)
	pairs := evidencePairs(60)
	bot := newFakeEvidenceBot()
	// An old bot: the limit is ignored and all 6000 closed trades come back.
	bot.state.liveTrades = func(instanceID string, status *string, limit, offset *int) (map[string]interface{}, error) {
		if instanceID != "strategy-4242-101" || status == nil || *status != "CLOSED" || limit == nil || *limit != 5000 || offset == nil || *offset != 0 {
			t.Fatalf("unexpected live trades call %s %v %v %v", instanceID, status, limit, offset)
		}
		return liveTradesPayload(6000, pairs), nil
	}
	bot.state.positions = func(instanceID string) (map[string]interface{}, error) { return positionsPayload(30, pairs), nil }
	bot.state.stats = func(instanceID string) (map[string]interface{}, error) {
		return map[string]interface{}{"success": true, "data": map[string]interface{}{"stats": map[string]interface{}{
			"total_open_positions": 30, "total_unrealized_pnl": 12.345, "total_unrealized_pnl_pct": 1.2345,
			"daily_pnl": 0, "daily_win_rate": 0, "max_drawdown": 0, "current_drawdown": 0,
		}}}, nil
	}
	bot.state.entryHalt = func(instanceID string) (map[string]interface{}, error) {
		return map[string]interface{}{"success": true, "data": map[string]interface{}{"halted": true, "unverified": false, "halt": map[string]interface{}{
			"id": 9, "kind": "max_drawdown", "instance_id": "strategy-4242-101", "network": "testnet", "address": "dydx1abcdefghijklmnop",
			"subaccount_number": 7, "reason": "drawdown limit reached on strategy-4242-101", "details": map[string]interface{}{"address": "dydx1abcdefghijklmnop"},
			"halted_at": "2026-09-25T09:30:00+00:00",
		}}}, nil
	}
	bot.state.cointegrated = func(instanceID string) (map[string]interface{}, error) {
		rows := make([]interface{}, 0, 20)
		for i := 0; i < 20; i++ {
			pair := strings.Split(pairs[i], "/")
			rows = append(rows, map[string]interface{}{"base_market": pair[0], "quote_market": pair[1], "hedge_ratio": 0.5, "half_life": 10.0 + float64(i),
				"zero_crossings": 40 - i, "p_value": 0.01, "z_score_mean": 0.0, "z_score_std": 1.0, "confidence_score": 0.9 - float64(i)/100, "analysis_timestamp": "2026-09-20T10:00:00+00:00"})
		}
		return map[string]interface{}{"success": true, "data": map[string]interface{}{"instance_id": instanceID, "analyzed_at": "2026-09-20T10:00:00+00:00", "count": 20, "pairs": rows}}, nil
	}
	builder := newEvidenceBuilder(t, conn, bot)
	strategy := evidenceTestStrategy()

	evidence := builder.Build(context.Background(), strategy, evidenceRunningState(t), nil, EvidenceOptions{IncludeLive: true, BotToken: "Bearer user-jwt"})
	live := evidence.Live
	if live == nil || !live.Available || !live.ActiveOrUnknown || live.Status != "running" || live.Network != "testnet" || live.LastConfirmedAt != "2026-09-26T10:00:00Z" {
		t.Fatalf("unexpected live block %+v", live)
	}
	if live.ClosedTrades == nil || live.ClosedTrades.Count != 5000 || !live.ClosedTrades.Truncated || len(live.ClosedTrades.Pairs) != 12 || live.ClosedTrades.PairsOmitted != 48 {
		t.Fatalf("expected 5000 capped trades over 12 kept pairs, got %+v", live.ClosedTrades)
	}
	if !evidenceNotesContain(evidence, "Only the newest 5000 of 6000 live closed trades were analysed.") || !evidenceNotesContain(evidence, evidenceNoteLiveSnapshot) {
		t.Fatalf("expected the live cap and snapshot notes, got %v", evidence.DataNotes)
	}
	if live.ClosedTrades.AvgDurationHours != 2 || live.ClosedTrades.WinRatePct != 75 {
		t.Fatalf("expected seconds converted to hours and a 75%% win rate, got %+v", live.ClosedTrades)
	}
	if len(live.OpenPositions) != 30 || live.OpenPositions[0].OpenHours != 4 || live.OpenPositions[0].ZScoreEntry == nil || *live.OpenPositions[0].ZScoreEntry != 2.1 {
		t.Fatalf("unexpected positions %+v", live.OpenPositions[:1])
	}
	if live.Exposure == nil || live.Exposure.OpenPositions != 30 || live.Exposure.TotalUnrealizedPnLUSD != 12.35 || live.Exposure.TotalUnrealizedPnLPct != 1.235 {
		t.Fatalf("unexpected exposure %+v", live.Exposure)
	}
	if live.EntryHalt == nil || !live.EntryHalt.Halted || live.EntryHalt.Kind != "max_drawdown" || live.EntryHalt.HaltedAt != "2026-09-25T09:30:00Z" || strings.Contains(live.EntryHalt.Reason, "4242") {
		t.Fatalf("unexpected entry halt %+v", live.EntryHalt)
	}
	if evidence.Cointegration == nil || evidence.Cointegration.Count != 20 || len(evidence.Cointegration.Pairs) != 12 || evidence.Cointegration.PairsOmitted != 8 || evidence.Cointegration.AnalyzedAt != "2026-09-20T10:00:00Z" {
		t.Fatalf("unexpected cointegration block %+v", evidence.Cointegration)
	}
	if evidence.Cointegration.Pairs[0].Pair != "A00-USD/B00-USD" || evidence.Cointegration.Pairs[0].ZeroCrossings == nil || *evidence.Cointegration.Pairs[0].ZeroCrossings != 40 {
		t.Fatalf("expected the most confident pair first, got %+v", evidence.Cointegration.Pairs[0])
	}
	summary := evidence.Summary
	if !summary.LiveAvailable || summary.LiveClosedTrades != 5000 || summary.LiveOpenPositions != 30 || summary.CointegratedPairs != 20 {
		t.Fatalf("unexpected summary %+v", summary)
	}

	// The caller's token is forwarded (without the Bearer prefix) because the
	// deployment does not use a service token.
	for _, token := range bot.state.tokens {
		if token != "Bearer user-jwt" {
			t.Fatalf("expected the caller's token on every bot call, got %q", token)
		}
	}

	// Secret freedom: nothing identifying the user, the account or the
	// deployment survives into the block, even though the payloads carry it.
	encoded, err := json.Marshal(evidence)
	if err != nil {
		t.Fatalf("encode evidence: %v", err)
	}
	text := string(encoded)
	for _, forbidden := range []string{"4242", "strategy-4242-101", "dydx1", "http://", "subaccount", "address", "instance_id", "bot-api", "details", "last_error", "user_id", "daily_pnl", "\"max_drawdown\":", "current_drawdown"} {
		if strings.Contains(text, forbidden) {
			t.Fatalf("evidence must not contain %q: %s", forbidden, text)
		}
	}
	if len(encoded) > evidenceMaxBytes {
		t.Fatalf("expected the evidence within %d bytes, got %d", evidenceMaxBytes, len(encoded))
	}
	indented, _ := json.MarshalIndent(evidence, "", "  ")
	t.Logf("fat live fixture evidence size: compact=%d bytes, indented=%d bytes", len(encoded), len(indented))
}

// TestEvidenceLiveTruncationFollowsTheBotTotal: the new bot honours the
// limit, so the cap never cuts the list; its total_trades says whether more
// closed trades exist than were read.
func TestEvidenceLiveTruncationFollowsTheBotTotal(t *testing.T) {
	conn := evidenceTestDB(t)
	pairs := evidencePairs(3)
	bot := newFakeEvidenceBot()
	total := 6000
	bot.state.liveTrades = func(instanceID string, status *string, limit, offset *int) (map[string]interface{}, error) {
		return liveTradesPage(total, limit, offset, pairs), nil
	}
	bot.state.positions = func(instanceID string) (map[string]interface{}, error) { return positionsPayload(1, pairs), nil }
	builder := newEvidenceBuilder(t, conn, bot)

	evidence := builder.Build(context.Background(), evidenceTestStrategy(), evidenceRunningState(t), nil, EvidenceOptions{IncludeLive: true})
	live := evidence.Live
	if live == nil || live.ClosedTrades == nil || live.ClosedTrades.Count != 5000 || !live.ClosedTrades.Truncated {
		t.Fatalf("expected the 5000-trade page marked truncated by the bot's total, got %+v", live)
	}
	if !evidenceNotesContain(evidence, "Only the newest 5000 of 6000 live closed trades were analysed.") {
		t.Fatalf("expected the truncation note with the bot's total, got %v", evidence.DataNotes)
	}

	total = 40
	again := builder.Build(context.Background(), evidenceTestStrategy(), evidenceRunningState(t), nil, EvidenceOptions{IncludeLive: true})
	if again.Live == nil || again.Live.ClosedTrades == nil || again.Live.ClosedTrades.Count != 40 || again.Live.ClosedTrades.Truncated {
		t.Fatalf("expected every trade analysed when the total fits the limit, got %+v", again.Live.ClosedTrades)
	}
	for _, note := range again.DataNotes {
		if strings.Contains(note, "live closed trades were analysed") {
			t.Fatalf("expected no truncation note, got %v", again.DataNotes)
		}
	}

	// Without total_trades the bot cannot signal truncation; only the cap can.
	trades, unknownTotal := parseBotLiveTrades(map[string]interface{}{"data": map[string]interface{}{"trades": liveTradesPayload(3, pairs)["data"].(map[string]interface{})["trades"]}})
	if unknownTotal != nil || len(trades) != 3 || aggregateLiveTrades(trades, nil, 5000, 12).Truncated {
		t.Fatalf("expected an unknown total and no truncation, got total=%v trades=%d", unknownTotal, len(trades))
	}
	if got := liveTradesTruncatedNote(5000, nil); got != "Only the newest 5000 live closed trades were analysed." {
		t.Fatalf("unexpected note without a total: %q", got)
	}
}

// TestEvidenceEmptyLedgerIsNeverCached: a run whose ledger comes back empty
// is reported as missing and read again on the next build.
func TestEvidenceEmptyLedgerIsNeverCached(t *testing.T) {
	conn := evidenceTestDB(t)
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 4242, strategyID: 101, runID: "run-0000-ffff", status: "completed", totalTrades: 0, winRate: floatPtr(0), drawdown: floatPtr(0), createdAt: time.Now().UTC()})
	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		return backtestTradesPayload(0, evidencePairs(1), nil, true), nil
	}
	builder := newEvidenceBuilder(t, conn, bot)

	evidence := builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions())
	if evidence.Backtests.LatestRun != nil || !evidenceNotesContain(evidence, evidenceNoteLedgerMissing) {
		t.Fatalf("expected an empty trade list reported as a missing ledger, got %+v %v", evidence.Backtests.LatestRun, evidence.DataNotes)
	}
	builder.Build(context.Background(), evidenceTestStrategy(), nil, nil, DefaultEvidenceOptions())
	if got := bot.callsOf("trades:"); got != 2 {
		t.Fatalf("expected the empty ledger not to be cached (two trade reads), got %d", got)
	}
	if builder.runs.size() != 0 {
		t.Fatalf("expected no cached ledger, got %d", builder.runs.size())
	}
}

func TestEvidenceLiveUnavailableOnBotTimeout(t *testing.T) {
	conn := evidenceTestDB(t)
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 4242, strategyID: 101, runID: "run-dddd-4444", status: "completed", totalTrades: 10, winRate: floatPtr(0.5), drawdown: floatPtr(3), createdAt: time.Now().UTC()})
	bot := newFakeEvidenceBot()
	bot.state.stall = true
	builder := newEvidenceBuilder(t, conn, bot)

	started := time.Now()
	evidence := builder.Build(context.Background(), evidenceTestStrategy(), evidenceRunningState(t), nil, EvidenceOptions{IncludeLive: true, LiveTimeout: 20 * time.Millisecond, LedgerTimeout: 20 * time.Millisecond})
	if elapsed := time.Since(started); elapsed > 2*time.Second {
		t.Fatalf("expected every stalled call bounded by its own deadline, took %s", elapsed)
	}
	if evidence.Live == nil || evidence.Live.Available || !evidence.Live.ActiveOrUnknown || evidence.Live.Status != "running" {
		t.Fatalf("expected an unavailable live block that still counts as active, got %+v", evidence.Live)
	}
	for _, note := range []string{evidenceNoteLiveUnavailable, evidenceNoteLedgerMissing, evidenceNotePairScanUnavailable} {
		if !evidenceNotesContain(evidence, note) {
			t.Fatalf("expected note %q, got %v", note, evidence.DataNotes)
		}
	}
	if len(evidence.Backtests.CompletedRuns) != 1 || evidence.Summary.LiveAvailable {
		t.Fatalf("expected the mirror runs kept and live marked unavailable, got %+v", evidence.Summary)
	}

	// An unknown runtime state counts as active and is never read.
	unknown := builder.Build(context.Background(), evidenceTestStrategy(), nil, errors.New("db down"), EvidenceOptions{IncludeLive: true})
	if unknown.Live == nil || unknown.Live.Available || !unknown.Live.ActiveOrUnknown || unknown.Live.Status != "unknown" || !evidenceNotesContain(unknown, evidenceNoteLiveUnavailable) {
		t.Fatalf("expected an unknown live block, got %+v", unknown.Live)
	}

	// Live data not requested: the runtime is not read, the pair scan still is.
	bot.state.stall = false
	bot.state.calls = nil
	skipped := builder.Build(context.Background(), evidenceTestStrategy(), evidenceRunningState(t), nil, EvidenceOptions{IncludeLive: false})
	if skipped.Live != nil || !evidenceNotesContain(skipped, evidenceNoteLiveSkipped) || !evidenceNotesContain(skipped, evidenceNoteNoPairScan) {
		t.Fatalf("expected no live block and the pair-scan note, got %+v %v", skipped.Live, skipped.DataNotes)
	}
	if bot.callsOf("live-trades:") != 0 || bot.callsOf("positions:") != 0 || bot.callsOf("cointegrated:") != 1 {
		t.Fatalf("expected only the pair scan read, got %v", bot.state.calls)
	}
}

func TestEvidenceTruncationKeepsTheBlockSmall(t *testing.T) {
	pairs := make([]EvidencePairStats, 0, 60)
	for i := 0; i < 60; i++ {
		pairs = append(pairs, EvidencePairStats{Pair: fmt.Sprintf("A%02d-USD/B%02d-USD", i, i), Trades: 10, Wins: 5, WinRatePct: 50, PnLUSD: float64(60 - i), AvgPnLPct: 1.5, AvgDurationHours: 6, MaxWinUSD: 20, MaxLossUSD: -10, ExitReasons: map[string]int{"timeout": 3, "stop_loss": 2, "zscore_cross": 5}})
	}
	positions := make([]EvidenceOpenPosition, 0, 30)
	for i := 0; i < 30; i++ {
		positions = append(positions, EvidenceOpenPosition{Pair: pairs[i].Pair, UnrealizedPnLUSD: 1, UnrealizedPnLPct: 0.5, ZScoreEntry: floatPtr(2), ZScoreCurrent: floatPtr(1), OpenHours: 3})
	}
	evidence := &StrategyEvidence{
		Backtests: EvidenceBacktests{LatestRun: &EvidenceLedger{RunRef: "run-eeee", Pairs: append([]EvidencePairStats{}, pairs...), Other: &pairs[0]}},
		Live:      &EvidenceLive{Available: true, ClosedTrades: &EvidenceLiveTrades{Count: 100, Pairs: append([]EvidencePairStats{}, pairs...)}, OpenPositions: positions},
		Cointegration: &EvidenceCointegration{Count: 20, Pairs: func() []EvidenceCointegratedPair {
			rows := make([]EvidenceCointegratedPair, 0, 20)
			for i := 0; i < 20; i++ {
				rows = append(rows, EvidenceCointegratedPair{Pair: pairs[i].Pair, HedgeRatio: floatPtr(0.5), HalfLife: floatPtr(12), PValue: floatPtr(0.01), Confidence: floatPtr(0.8)})
			}
			return rows
		}()},
		DataNotes: []string{},
	}
	before, _ := json.Marshal(evidence)
	if !truncateEvidence(evidence, 4*1024) {
		t.Fatal("expected the oversized evidence to be truncated")
	}
	encoded, _ := json.Marshal(evidence)
	// The ladder ends at 4 pairs per ledger, 10 positions and 6 scan rows;
	// this fixture lands just above 4 KB there and far below the 16 KB cap.
	if len(encoded) > 6*1024 || len(encoded) >= len(before)/4 {
		t.Fatalf("expected a much smaller block after truncation, got %d bytes (from %d)", len(encoded), len(before))
	}
	ledger := evidence.Backtests.LatestRun
	if ledger.Other != nil || len(ledger.Pairs) > 8 || ledger.PairsOmitted < 52 || len(evidence.Live.OpenPositions) > 10 || len(evidence.Cointegration.Pairs) > 6 || evidence.Cointegration.PairsOmitted < 14 {
		t.Fatalf("unexpected truncation result: pairs=%d omitted=%d positions=%d coint=%d", len(ledger.Pairs), ledger.PairsOmitted, len(evidence.Live.OpenPositions), len(evidence.Cointegration.Pairs))
	}
	small := &StrategyEvidence{DataNotes: []string{}}
	if truncateEvidence(small, evidenceMaxBytes) {
		t.Fatal("expected a small evidence untouched")
	}
}

func TestEvidenceSettingsFromConfig(t *testing.T) {
	settings := evidenceSettingsFromConfig(`{"request":{"trading_parameters":{"zscore_threshold":"2.5","stats_window":50.0,"max_half_life":30,"resolution":"4h","close_at_zscore_cross":true,"usd_per_trade":250,"rebalance_interval_hours":6.5,"runtime_subaccount":3}}}`)
	if settings["zscore_threshold"] != 2.5 || settings["stats_window"] != 50 || settings["max_half_life"] != 30 || settings["candle_resolution"] != "4HOURS" || settings["close_at_zscore_cross"] != true || settings["usd_per_trade"] != 250.0 {
		t.Fatalf("unexpected settings %+v", settings)
	}
	if _, ok := settings["rebalance_interval_hours"]; ok {
		t.Fatalf("expected a fractional whole-number setting dropped, got %+v", settings)
	}
	if _, ok := settings["runtime_subaccount"]; ok {
		t.Fatalf("expected non-allowlisted keys dropped, got %+v", settings)
	}
	if evidenceSettingsFromConfig("") != nil || evidenceSettingsFromConfig("not json") != nil || evidenceSettingsFromConfig(`{"other":1}`) != nil {
		t.Fatal("expected no settings from empty, broken or unrelated snapshots")
	}
}

func TestEvidencePairStatsForStrategyOwnershipAndUnwiredService(t *testing.T) {
	unwired := NewAIMarketService(nil)
	pairs, cointegrated, notes, err := unwired.PairStatsForStrategy(context.Background(), 1, false, 1, "")
	if err != nil || pairs != nil || cointegrated != nil || len(notes) != 1 {
		t.Fatalf("expected an unwired service to answer with a note, got %v %v %v %v", pairs, cointegrated, notes, err)
	}

	conn := evidenceTestDB(t)
	for _, user := range []int{1, 2} {
		if _, err := conn.Exec(`INSERT INTO users (id, username, email) VALUES (?, ?, ?)`, user, fmt.Sprintf("evidence-user-%d", user), fmt.Sprintf("evidence-user-%d@example.local", user)); err != nil {
			t.Fatalf("insert user: %v", err)
		}
	}
	strategies := NewStrategyService(repository.NewStrategyRepository(conn))
	strategy, err := strategies.CreateStrategy(1, "Majors", "desc", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 1, strategyID: strategy.ID, runID: "run-ffff-5555", status: "completed", totalTrades: 6, winRate: floatPtr(0.5), drawdown: floatPtr(3), createdAt: time.Now().UTC()})
	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		return backtestTradesPayload(6, []string{"BTC-USD/ETH-USD", "SOL-USD/AVAX-USD"}, nil, true), nil
	}
	service := NewAIMarketService(nil)
	service.SetStrategyEvidence(newEvidenceBuilder(t, conn, bot), strategies, repository.NewBacktestRepository(conn))

	pairs, cointegrated, notes, err = service.PairStatsForStrategy(context.Background(), 1, false, strategy.ID, "user-jwt")
	if err != nil || len(pairs) != 2 || len(cointegrated) != 0 || !containsNote(notes, evidenceNoteNeverStarted) {
		t.Fatalf("unexpected pair stats %v %v %v %v", pairs, cointegrated, notes, err)
	}
	if bot.callsOf("live-trades:") != 0 {
		t.Fatal("expected market selection not to read the live runtime")
	}
	// The caller's token reached the ledger read (no service token configured).
	if len(bot.state.tokens) == 0 {
		t.Fatal("expected the ledger to be read from the bot")
	}
	for _, token := range bot.state.tokens {
		if token != "user-jwt" {
			t.Fatalf("expected the caller's bot token on every bot call, got %q", token)
		}
	}
	_, _, _, err = service.PairStatsForStrategy(context.Background(), 2, false, strategy.ID, "")
	var requestErr *AIRequestError
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 for a foreign strategy, got %v", err)
	}
	if _, _, _, err := service.PairStatsForStrategy(context.Background(), 2, true, strategy.ID, ""); err != nil {
		t.Fatalf("expected admins to read any strategy, got %v", err)
	}
	if _, _, _, err := service.PairStatsForStrategy(context.Background(), 1, false, strategy.ID+50, ""); !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 for a missing strategy, got %v", err)
	}
}

func TestEvidenceRunCacheSharesOneFetchAndEvicts(t *testing.T) {
	cache := newEvidenceRunCache(time.Hour, 2)
	now := time.Date(2026, 9, 26, 12, 0, 0, 0, time.UTC)
	cache.now = func() time.Time { return now }

	builds := 0
	var wg sync.WaitGroup
	release := make(chan struct{})
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = cache.getOrBuild("a", func() (*EvidenceLedger, error) {
				<-release
				builds++
				return &EvidenceLedger{RunRef: "a"}, nil
			})
		}()
	}
	time.Sleep(20 * time.Millisecond)
	close(release)
	wg.Wait()
	if builds != 1 {
		t.Fatalf("expected one shared build, got %d", builds)
	}
	if _, err := cache.getOrBuild("b", func() (*EvidenceLedger, error) { return nil, errors.New("boom") }); err == nil || cache.size() != 1 {
		t.Fatalf("expected a failed build not to be cached, size %d err %v", cache.size(), err)
	}
	_, _ = cache.getOrBuild("b", func() (*EvidenceLedger, error) { return &EvidenceLedger{RunRef: "b"}, nil })
	now = now.Add(time.Minute)
	_, _ = cache.getOrBuild("c", func() (*EvidenceLedger, error) { return &EvidenceLedger{RunRef: "c"}, nil })
	if cache.size() != 2 {
		t.Fatalf("expected the capacity respected, got %d entries", cache.size())
	}
	rebuilt := false
	_, _ = cache.getOrBuild("a", func() (*EvidenceLedger, error) { rebuilt = true; return &EvidenceLedger{RunRef: "a"}, nil })
	if !rebuilt {
		t.Fatal("expected the least recently used entry evicted")
	}
	now = now.Add(2 * time.Hour)
	rebuilt = false
	_, _ = cache.getOrBuild("c", func() (*EvidenceLedger, error) { rebuilt = true; return &EvidenceLedger{RunRef: "c"}, nil })
	if !rebuilt {
		t.Fatal("expected an expired entry rebuilt")
	}
}

// TestStrategyChatTurnCarriesEvidence runs a chat turn with the evidence
// builder wired: the system prompt carries the ledger and live blocks, the
// assistant message carries the evidence summary, and a mirror without the
// config column (older schema) only costs the settings snapshot.
func TestStrategyChatTurnCarriesEvidence(t *testing.T) {
	t.Setenv("BOT_API_TOKEN", "chat-evidence-service-token")
	t.Setenv("BOT_API_USE_SERVICE_TOKEN", "false")
	f := newStrategyChatFixture(t)
	now := time.Now().UTC()
	if _, err := f.db.Exec(`INSERT INTO backtest_runs (user_id, strategy_id, run_id, status, start_date, end_date, total_trades, win_rate, total_pnl_usd, max_drawdown, created_at)
		VALUES (1, ?, 'chat-run-0001', 'completed', '2026-06-01', '2026-09-01', 9, 0.55, 42.5, 8.0, ?)`, f.strategyID, now); err != nil {
		t.Fatalf("insert run: %v", err)
	}
	f.setRuntime(t, true, `{"status":"running","bot_status":"running","instance_id":"strategy-1-`+fmt.Sprint(f.strategyID)+`","network":"testnet"}`)

	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		return backtestTradesPayload(9, []string{"BTC-USD/ETH-USD", "SOL-USD/AVAX-USD"}, nil, true), nil
	}
	bot.state.liveTrades = func(instanceID string, status *string, limit, offset *int) (map[string]interface{}, error) {
		if instanceID != "strategy-1-"+fmt.Sprint(f.strategyID) {
			t.Fatalf("unexpected instance id %s", instanceID)
		}
		return liveTradesPayload(4, []string{"BTC-USD/ETH-USD"}), nil
	}
	bot.state.positions = func(instanceID string) (map[string]interface{}, error) {
		return positionsPayload(1, []string{"BTC-USD/ETH-USD"}), nil
	}
	f.service.SetEvidenceBuilder(newEvidenceBuilder(t, f.db, bot))
	f.ai.content = `{"reply":"BTC-USD/ETH-USD carried the run.","proposal":null}`

	turn, err := f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "Which pair works?", BotToken: "user-jwt"})
	if err != nil {
		t.Fatalf("SendMessage: %v", err)
	}
	system := f.ai.requests[0].System
	for _, expected := range []string{`"latest_run"`, `"BTC-USD/ETH-USD"`, `"live"`, `"closed_trades"`, `"open_positions"`, `"run_ref": "chat-run"`, `"win_rate_pct": 55`, "pair statistics", "snapshot taken when this reply was prepared"} {
		if !strings.Contains(system, expected) {
			t.Fatalf("expected %q in the system prompt:\n%s", expected, system)
		}
	}
	for _, forbidden := range []string{"strategy-1-", "runtime_subaccount", "user_id", "instance_id"} {
		if strings.Contains(system, forbidden) {
			t.Fatalf("system prompt must not contain %q", forbidden)
		}
	}
	for _, token := range bot.state.tokens {
		if token != "user-jwt" {
			t.Fatalf("expected the caller's token on bot calls, got %q", token)
		}
	}
	user, assistant := turn.Messages[0], turn.Messages[1]
	if user.EvidenceSummary != nil {
		t.Fatalf("expected no evidence summary on the user message, got %+v", user.EvidenceSummary)
	}
	summary := assistant.EvidenceSummary
	if summary == nil || summary.CompletedRuns != 1 || summary.TradesAnalysed != 9 || summary.PairsAnalysed != 2 || !summary.LiveAvailable || summary.LiveClosedTrades != 4 || summary.LiveOpenPositions != 1 {
		t.Fatalf("unexpected evidence summary %+v", summary)
	}
	encoded, _ := json.Marshal(assistant)
	if !strings.Contains(string(encoded), `"evidence_summary":{"completed_runs":1`) {
		t.Fatalf("expected the evidence summary in the message JSON: %s", encoded)
	}
	t.Logf("assistant message JSON:\n%s", encoded)

	// Messages loaded later carry no summary (null), like rows from before.
	state, err := f.service.GetChat(StrategyChatActor{UserID: 1}, f.strategyID)
	if err != nil || len(state.Messages) != 2 || state.Messages[1].EvidenceSummary != nil {
		t.Fatalf("expected null evidence summaries on loaded messages, got %+v %v", state.Messages, err)
	}
	loaded, _ := json.Marshal(state.Messages[1])
	if !strings.Contains(string(loaded), `"evidence_summary":null`) {
		t.Fatalf("expected evidence_summary null on loaded rows: %s", loaded)
	}
}
