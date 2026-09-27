package services

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
	"github.com/dydx-trading-bot/backend-go/internal/repository"
	_ "modernc.org/sqlite"
)

// strategyChatTestSchema is the part of the schema the chat touches, as sqlite.
var strategyChatTestSchema = []string{
	`CREATE TABLE users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		username TEXT NOT NULL UNIQUE,
		email TEXT NOT NULL UNIQUE,
		hashed_password TEXT NOT NULL DEFAULT '',
		is_active BOOLEAN NOT NULL DEFAULT 1,
		is_admin BOOLEAN NOT NULL DEFAULT 0,
		max_strategies INTEGER DEFAULT 10,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`,
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
	`CREATE TABLE strategy_execution_states (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		strategy_id INTEGER NOT NULL UNIQUE,
		is_running BOOLEAN NOT NULL DEFAULT 0,
		last_run_at DATETIME,
		next_run_at DATETIME,
		state TEXT,
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL
	)`,
	`CREATE TABLE strategy_version_history (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		strategy_id INTEGER NOT NULL,
		version_number INTEGER NOT NULL,
		change_description TEXT,
		config_snapshot TEXT NOT NULL,
		changes TEXT,
		created_at DATETIME,
		created_by_user_id INTEGER,
		UNIQUE (strategy_id, version_number)
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
		created_at DATETIME NOT NULL
	)`,
	`CREATE TABLE strategy_chat_sessions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		strategy_id INTEGER NOT NULL,
		title TEXT NOT NULL DEFAULT '',
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		archived_at DATETIME
	)`,
	`CREATE TABLE strategy_chat_messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id INTEGER NOT NULL REFERENCES strategy_chat_sessions (id) ON DELETE CASCADE,
		role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
		content TEXT NOT NULL,
		proposal TEXT,
		proposal_status TEXT CHECK (proposal_status IN ('pending', 'applied', 'created', 'dismissed')),
		proposal_result TEXT,
		provider TEXT NOT NULL DEFAULT '',
		model TEXT NOT NULL DEFAULT '',
		input_tokens INTEGER NOT NULL DEFAULT 0,
		output_tokens INTEGER NOT NULL DEFAULT 0,
		created_at DATETIME NOT NULL
	)`,
}

type fakeStrategyChatAI struct {
	content  string
	err      error
	requests []AIChatCompletionRequest
	provider string
}

func (f *fakeStrategyChatAI) ChatCompletion(_ context.Context, _ int, provider string, req AIChatCompletionRequest) (*AIChatCompletionResult, error) {
	f.requests = append(f.requests, req)
	f.provider = provider
	if f.err != nil {
		return nil, f.err
	}
	return &AIChatCompletionResult{Provider: provider, Model: "grok-4.3", Content: f.content, InputTokens: 100, OutputTokens: 20}, nil
}

type strategyChatFixture struct {
	db         *sql.DB
	service    *StrategyChatService
	strategies *StrategyService
	ai         *fakeStrategyChatAI
	strategyID int
}

func newStrategyChatFixture(t *testing.T) *strategyChatFixture {
	t.Helper()
	// The repositories gate FOR UPDATE on the driver name.
	t.Setenv("DB_TYPE", "sqlite")
	conn, err := sql.Open("sqlite", "file:"+strings.ReplaceAll(t.Name(), "/", "_")+"?mode=memory&cache=shared")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	conn.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = conn.Close() })
	for _, statement := range strategyChatTestSchema {
		if _, err := conn.Exec(statement); err != nil {
			t.Fatalf("create schema: %v", err)
		}
	}
	for _, user := range []struct {
		id  int
		max int
	}{{1, 10}, {2, 10}} {
		if _, err := conn.Exec(`INSERT INTO users (id, username, email, max_strategies) VALUES (?, ?, ?, ?)`,
			user.id, "user"+string(rune('0'+user.id)), "user"+string(rune('0'+user.id))+"@example.local", user.max); err != nil {
			t.Fatalf("insert user: %v", err)
		}
	}

	strategies := NewStrategyService(repository.NewStrategyRepository(conn))
	source, err := strategies.CreateStrategy(1, "Majors pairs", "BTC/ETH pairs", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	source.MaxDrawdownPct = 15
	source.RuntimeSubaccount = 3
	source.AbortAllPositions = true
	source.IsPublic = true
	source.SetSelectedMarketList([]string{"BTC-USD", "ETH-USD"})
	if err := strategies.UpdateStrategy(source); err != nil {
		t.Fatalf("update strategy: %v", err)
	}

	ai := &fakeStrategyChatAI{content: `{"reply":"Raise the entry threshold a little.","proposal":{"kind":"update","title":"Fewer entries","summary":"Trade less often.","suggested_name":"","changes":[{"field":"zscore_threshold","value":2.0,"reason":"Fewer weak signals."},{"field":"place_trades","value":false,"reason":"no"}]}}`}
	service := NewStrategyChatService(
		repository.NewStrategyChatRepository(conn),
		strategies,
		repository.NewBacktestRepository(conn),
		repository.NewUserRepository(conn),
		ai,
	)
	return &strategyChatFixture{db: conn, service: service, strategies: strategies, ai: ai, strategyID: source.ID}
}

func (f *strategyChatFixture) count(t *testing.T, table string) int {
	t.Helper()
	var count int
	if err := f.db.QueryRow(`SELECT COUNT(*) FROM ` + table).Scan(&count); err != nil {
		t.Fatalf("count %s: %v", table, err)
	}
	return count
}

func (f *strategyChatFixture) setRuntime(t *testing.T, isRunning bool, state string) {
	t.Helper()
	now := time.Now().UTC()
	if _, err := f.db.Exec(`INSERT INTO strategy_execution_states (strategy_id, is_running, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)`,
		f.strategyID, isRunning, state, now, now); err != nil {
		t.Fatalf("insert execution state: %v", err)
	}
}

func (f *strategyChatFixture) sendTurn(t *testing.T) *StrategyChatTurn {
	t.Helper()
	turn, err := f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "Should I trade less often?"})
	if err != nil {
		t.Fatalf("SendMessage: %v", err)
	}
	return turn
}

func expectStrategyChatError(t *testing.T, err error, status int, code string) {
	t.Helper()
	var chatErr *StrategyChatError
	if !errors.As(err, &chatErr) || chatErr.Status != status || chatErr.Code != code {
		t.Fatalf("expected %d %s, got %#v", status, code, err)
	}
}

func TestStrategyChatSendMessageStoresTurnWithValidatedProposal(t *testing.T) {
	f := newStrategyChatFixture(t)
	now := time.Now().UTC()
	for _, run := range []struct {
		runID      string
		strategyID int
		status     string
	}{
		{"mine-completed-0001", f.strategyID, "completed"},
		{"mine-running-000002", f.strategyID, "running"},
		{"other-completed-003", f.strategyID + 100, "completed"},
	} {
		if _, err := f.db.Exec(`INSERT INTO backtest_runs (user_id, strategy_id, run_id, status, start_date, end_date, total_trades, win_rate, total_pnl_usd, max_drawdown, created_at)
			VALUES (1, ?, ?, ?, '2026-06-01', '2026-09-01', 25, 55.0, 42.5, 8.0, ?)`, run.strategyID, run.runID, run.status, now); err != nil {
			t.Fatalf("insert run: %v", err)
		}
	}
	f.setRuntime(t, false, `{"status":"stopped","bot_status":"stopped","instance_id":"strategy-1-1"}`)

	turn := f.sendTurn(t)
	if f.ai.provider != ExternalAPIProviderGrok {
		t.Fatalf("expected grok as the default provider, got %q", f.ai.provider)
	}
	request := f.ai.requests[0]
	if !strings.Contains(request.System, `"run_ref": "mine-com"`) || strings.Contains(request.System, "other-co") || strings.Contains(request.System, "mine-run") {
		t.Fatalf("expected only this strategy's completed run in the context:\n%s", request.System)
	}
	if strings.Contains(request.System, "strategy-1-1") || strings.Contains(request.System, `"runtime_subaccount"`) {
		t.Fatalf("expected no instance id or subaccount in the context")
	}
	if request.Schema == nil || request.MaxOutputTokens != 16000 || len(request.Turns) != 1 {
		t.Fatalf("unexpected AI request %+v", request)
	}

	if turn.Session == nil || turn.Session.ID == 0 || turn.Session.Title != "Should I trade less often?" || len(turn.Messages) != 2 {
		t.Fatalf("unexpected turn %+v", turn)
	}
	assistant := turn.Messages[1]
	if assistant.Role != "assistant" || assistant.ProposalStatus == nil || *assistant.ProposalStatus != "pending" || assistant.Model != "grok-4.3" {
		t.Fatalf("unexpected assistant message %+v", assistant)
	}
	if len(assistant.Proposal.Changes) != 1 || assistant.Proposal.Changes[0].Field != "zscore_threshold" || assistant.Proposal.Changes[0].Current != 1.5 {
		t.Fatalf("expected the zscore change with server-read current value, got %+v", assistant.Proposal)
	}
	if len(assistant.Proposal.Dropped) != 1 || assistant.Proposal.Dropped[0].Field != "place_trades" {
		t.Fatalf("expected place_trades dropped, got %+v", assistant.Proposal.Dropped)
	}
	if f.count(t, "strategy_chat_messages") != 2 || f.count(t, "strategy_chat_sessions") != 1 {
		t.Fatal("expected one session with two messages")
	}

	// The second turn re-sends the history with a note of the proposal.
	f.sendTurn(t)
	second := f.ai.requests[1]
	if len(second.Turns) != 3 || !strings.Contains(second.Turns[1].Content, "Status: pending") {
		t.Fatalf("expected history with the proposal note, got %+v", second.Turns)
	}

	state, err := f.service.GetChat(StrategyChatActor{UserID: 1}, f.strategyID)
	if err != nil || state.Session == nil || len(state.Messages) != 4 || state.RuntimeActive {
		t.Fatalf("unexpected chat state %+v %v", state, err)
	}
}

func TestStrategyChatFailedTurnStoresNothing(t *testing.T) {
	f := newStrategyChatFixture(t)
	f.ai.err = &aiProviderCallError{StatusCode: http.StatusInternalServerError, Message: "AI provider returned status 500"}
	_, err := f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "hello"})
	expectStrategyChatError(t, err, http.StatusBadGateway, StrategyChatCodeProviderError)
	if f.count(t, "strategy_chat_sessions") != 0 || f.count(t, "strategy_chat_messages") != 0 {
		t.Fatal("expected nothing persisted after a failed turn")
	}

	f.ai.err = &AIProviderAccessError{Code: http.StatusConflict, Message: "Grok is not configured with active credentials"}
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "hello"})
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeProviderNotConfigured)

	f.ai.err = &aiReplyCutOffError{}
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "hello"})
	expectStrategyChatError(t, err, http.StatusBadGateway, StrategyChatCodeProviderError)

	f.ai.err = context.DeadlineExceeded
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "hello"})
	expectStrategyChatError(t, err, http.StatusGatewayTimeout, StrategyChatCodeTimeout)

	f.ai.err = nil
	f.ai.content = `{"reply":"cut`
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "hello"})
	expectStrategyChatError(t, err, http.StatusBadGateway, StrategyChatCodeProviderError)
	if f.count(t, "strategy_chat_messages") != 0 {
		t.Fatal("expected nothing persisted after an unreadable reply")
	}
}

func TestStrategyChatInputValidationAndOwnership(t *testing.T) {
	f := newStrategyChatFixture(t)
	_, err := f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "   "})
	expectStrategyChatError(t, err, http.StatusBadRequest, StrategyChatCodeInvalidRequest)
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: strings.Repeat("a", 4001)})
	expectStrategyChatError(t, err, http.StatusBadRequest, StrategyChatCodeInvalidRequest)
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{Content: "hi", Provider: "gemini"})
	expectStrategyChatError(t, err, http.StatusBadRequest, StrategyChatCodeInvalidRequest)
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 2}, f.strategyID, StrategyChatSendInput{Content: "hi"})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
	if len(f.ai.requests) != 0 {
		t.Fatal("expected no provider call for refused requests")
	}

	// An admin may open another user's strategy; the session is the admin's.
	if _, err := f.service.GetChat(StrategyChatActor{UserID: 2, IsAdmin: true}, f.strategyID); err != nil {
		t.Fatalf("expected admin access, got %v", err)
	}

	if err := f.strategies.DeleteStrategy(f.strategyID); err != nil {
		t.Fatalf("delete strategy: %v", err)
	}
	_, err = f.service.GetChat(StrategyChatActor{UserID: 1}, f.strategyID)
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
}

func TestStrategyChatApplyWritesSnapshotAndNeedsRunningAck(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	messageID := turn.Messages[1].ID
	f.setRuntime(t, false, `{"status":"running","bot_status":"running"}`)

	_, err := f.service.ApplyProposal(StrategyChatActor{UserID: 2}, f.strategyID, messageID, StrategyChatApplyInput{AcknowledgeRunning: true})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)

	_, err = f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{})
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeRunningAckRequired)

	unknown := []string{"stats_window"}
	_, err = f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{Fields: &unknown, AcknowledgeRunning: true})
	expectStrategyChatError(t, err, http.StatusBadRequest, StrategyChatCodeInvalidProposalFields)
	empty := []string{}
	_, err = f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{Fields: &empty, AcknowledgeRunning: true})
	expectStrategyChatError(t, err, http.StatusBadRequest, StrategyChatCodeInvalidProposalFields)

	before, _ := f.strategies.GetStrategy(f.strategyID)
	fields := []string{"zscore_threshold"}
	result, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{Fields: &fields, AcknowledgeRunning: true})
	if err != nil {
		t.Fatalf("ApplyProposal: %v", err)
	}
	if result.Strategy.ZscoreThreshold != 2.0 {
		t.Fatalf("expected zscore 2.0, got %v", result.Strategy.ZscoreThreshold)
	}
	stored, _ := f.strategies.GetStrategy(f.strategyID)
	if stored.ZscoreThreshold != 2.0 || stored.PlaceTrades != before.PlaceTrades || stored.RuntimeSubaccount != before.RuntimeSubaccount {
		t.Fatalf("expected only zscore_threshold to change, got %+v", stored)
	}

	message := result.Message
	if message.ProposalStatus == nil || *message.ProposalStatus != "applied" || message.ProposalResult == nil ||
		message.ProposalResult.VersionID == nil || message.ProposalResult.AppliedFields == nil || len(*message.ProposalResult.AppliedFields) != 1 ||
		message.ProposalResult.UnchangedFields == nil || len(*message.ProposalResult.UnchangedFields) != 0 ||
		message.ProposalResult.AcknowledgedRunning == nil || !*message.ProposalResult.AcknowledgedRunning || message.ProposalResult.At == "" {
		t.Fatalf("unexpected applied message %+v", message)
	}
	if result.AuditDetails == nil || result.AuditDetails["version_id"] != *message.ProposalResult.VersionID {
		t.Fatalf("expected audit details with the version id, got %+v", result.AuditDetails)
	}

	history, err := f.strategies.GetVersionHistory(f.strategyID)
	if err != nil || len(history) != 1 || history[0].ID != *message.ProposalResult.VersionID || history[0].Version != 1 {
		t.Fatalf("expected one version snapshot, got %+v %v", history, err)
	}
	// The snapshot is exactly what RevertVersion reads back.
	var restored models.BacktestStrategy
	if err := restored.FromJSON([]byte(history[0].StrategyData.String)); err != nil {
		t.Fatalf("decode snapshot: %v", err)
	}
	if restored.ZscoreThreshold != 1.5 || restored.MaxDrawdownPct != 15 || restored.Name != before.Name {
		t.Fatalf("expected the before-state in the snapshot, got %+v", restored)
	}

	_, err = f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{AcknowledgeRunning: true})
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeProposalNotPending)
	_, err = f.service.DismissProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID)
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeProposalNotPending)
}

func TestStrategyChatApplyNeedsAckWhenRuntimeStateIsUnknown(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	f.setRuntime(t, false, `{broken`)
	_, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID, StrategyChatApplyInput{})
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeRunningAckRequired)
}

func TestStrategyChatApplyOnStoppedStrategyNeedsNoAck(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	result, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID, StrategyChatApplyInput{})
	if err != nil {
		t.Fatalf("ApplyProposal: %v", err)
	}
	if result.Message.ProposalResult.AcknowledgedRunning != nil {
		t.Fatal("expected no acknowledgement recorded for a never-started strategy")
	}
}

func TestStrategyChatUserMessageHasNoProposal(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	_, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[0].ID, StrategyChatApplyInput{})
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeProposalNotPending)
	_, err = f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, 99999, StrategyChatApplyInput{})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
}

func TestStrategyChatCreateStrategyCopiesSettingsAndForcesIdentity(t *testing.T) {
	f := newStrategyChatFixture(t)
	f.ai.content = `{"reply":"A slower variant.","proposal":{"kind":"new_strategy","title":"Slower variant","summary":"s","suggested_name":"Majors slow","changes":[{"field":"stats_window","value":42,"reason":"Longer window."},{"field":"resolution","value":"4HOURS","reason":"Slower bars."}]}}`
	turn := f.sendTurn(t)
	messageID := turn.Messages[1].ID
	source, _ := f.strategies.GetStrategy(f.strategyID)

	result, err := f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatCreateInput{})
	if err != nil {
		t.Fatalf("CreateStrategyFromProposal: %v", err)
	}
	created := result.Strategy
	if created.ID == source.ID || created.UserID != 1 || created.Name != "Majors slow" {
		t.Fatalf("unexpected new strategy identity %+v", created)
	}
	if created.IsPublic || created.IsDefault || created.AbortAllPositions {
		t.Fatalf("expected visibility, default and abort flags forced off, got %+v", created)
	}
	if created.StatsWindow != 42 || created.CandleResolution != "4HOURS" {
		t.Fatalf("expected the changes applied, got stats_window=%d resolution=%s", created.StatsWindow, created.CandleResolution)
	}
	if created.MaxDrawdownPct != 15 || created.RuntimeSubaccount != 3 || len(created.SelectedMarketList()) != 2 || created.Description != source.Description {
		t.Fatalf("expected the source settings copied, got %+v", created)
	}

	after, _ := f.strategies.GetStrategy(f.strategyID)
	if after.StatsWindow != source.StatsWindow || after.CandleResolution != source.CandleResolution || after.UsageCount != source.UsageCount {
		t.Fatalf("expected the source strategy untouched, got %+v", after)
	}
	message := result.Message
	if message.ProposalStatus == nil || *message.ProposalStatus != "created" || message.ProposalResult.NewStrategyID == nil ||
		*message.ProposalResult.NewStrategyID != created.ID || message.ProposalResult.NewStrategyName != "Majors slow" {
		t.Fatalf("unexpected created message %+v", message)
	}
	if result.AuditDetails["source_strategy_id"] != f.strategyID {
		t.Fatalf("expected the source id in the audit details, got %+v", result.AuditDetails)
	}
}

func TestStrategyChatCreateStrategyEnforcesQuota(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	if _, err := f.db.Exec(`UPDATE users SET max_strategies = 1 WHERE id = 1`); err != nil {
		t.Fatalf("set quota: %v", err)
	}
	_, err := f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID, StrategyChatCreateInput{Name: "Copy"})
	expectStrategyChatError(t, err, http.StatusTooManyRequests, StrategyChatCodeQuotaExceeded)
	if f.count(t, "backtest_strategies") != 1 {
		t.Fatal("expected no strategy created over quota")
	}
	message, _ := f.service.repo.GetMessage(turn.Messages[1].ID)
	if message.ProposalStatus.String != "pending" {
		t.Fatalf("expected the proposal to stay pending, got %q", message.ProposalStatus.String)
	}

	long := strings.Repeat("n", 101)
	if _, err := f.db.Exec(`UPDATE users SET max_strategies = 10 WHERE id = 1`); err != nil {
		t.Fatalf("reset quota: %v", err)
	}
	_, err = f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID, StrategyChatCreateInput{Name: long})
	expectStrategyChatError(t, err, http.StatusBadRequest, StrategyChatCodeInvalidRequest)
}

func TestStrategyChatDismissAndNewSession(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	message, err := f.service.DismissProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID)
	if err != nil || message.ProposalStatus == nil || *message.ProposalStatus != "dismissed" || message.ProposalResult == nil {
		t.Fatalf("unexpected dismiss result %+v %v", message, err)
	}
	_, err = f.service.DismissProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID)
	expectStrategyChatError(t, err, http.StatusConflict, StrategyChatCodeProposalNotPending)

	fresh, err := f.service.StartSession(StrategyChatActor{UserID: 1}, f.strategyID)
	if err != nil || fresh.Session.ID == turn.Session.ID || len(fresh.Messages) != 0 {
		t.Fatalf("expected a new empty session, got %+v %v", fresh, err)
	}
	state, err := f.service.GetChat(StrategyChatActor{UserID: 1}, f.strategyID)
	if err != nil || state.Session.ID != fresh.Session.ID || len(state.Messages) != 0 {
		t.Fatalf("expected the new session to be current, got %+v %v", state, err)
	}
	old := turn.Session.ID
	_, err = f.service.SendMessage(context.Background(), StrategyChatActor{UserID: 1}, f.strategyID, StrategyChatSendInput{SessionID: &old, Content: "hi"})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
}

func TestStrategyChatProposalJSONRoundTrip(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	stored, err := f.service.repo.GetMessage(turn.Messages[1].ID)
	if err != nil || !stored.Proposal.Valid {
		t.Fatalf("expected a stored proposal, got %+v %v", stored, err)
	}
	var raw map[string]any
	if err := json.Unmarshal([]byte(stored.Proposal.String), &raw); err != nil {
		t.Fatalf("stored proposal is not JSON: %v", err)
	}
	for _, key := range []string{"kind", "title", "summary", "suggested_name", "changes", "dropped"} {
		if _, ok := raw[key]; !ok {
			t.Fatalf("expected %s in the stored proposal, got %v", key, raw)
		}
	}
}

// exec runs a statement on the fixture database, such as creating a trigger
// that stands in for a concurrent writer or a failing statement.
func (f *strategyChatFixture) exec(t *testing.T, statement string, args ...any) {
	t.Helper()
	if _, err := f.db.Exec(statement, args...); err != nil {
		t.Fatalf("exec %q: %v", statement, err)
	}
}

func (f *strategyChatFixture) messageStatus(t *testing.T, messageID int64) (string, bool) {
	t.Helper()
	message, err := f.service.repo.GetMessage(messageID)
	if err != nil || message == nil {
		t.Fatalf("load message %d: %v", messageID, err)
	}
	return message.ProposalStatus.String, message.ProposalResult.Valid
}

// A writer that lands between the apply's read and its write (here a trigger
// on the version snapshot) is not reverted, because only the applied columns
// are written.
func TestStrategyChatApplyWritesOnlyTheAppliedColumns(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	f.exec(t, `CREATE TRIGGER concurrent_write AFTER INSERT ON strategy_version_history
		BEGIN UPDATE backtest_strategies SET place_trades = 0, stop_loss_pct = 1.0 WHERE id = NEW.strategy_id; END`)

	fields := []string{"zscore_threshold"}
	if _, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID, StrategyChatApplyInput{Fields: &fields}); err != nil {
		t.Fatalf("ApplyProposal: %v", err)
	}
	stored, _ := f.strategies.GetStrategy(f.strategyID)
	if stored.ZscoreThreshold != 2.0 || stored.PlaceTrades || stored.StopLossPct != 1.0 {
		t.Fatalf("expected the concurrent place_trades/stop_loss change preserved next to zscore 2.0, got %+v", stored)
	}
}

// A failing strategy write rolls the whole apply back: the proposal stays
// pending, no snapshot is kept, and the apply succeeds once the failure is gone.
func TestStrategyChatApplyFailureLeavesProposalPending(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	messageID := turn.Messages[1].ID
	f.exec(t, `CREATE TRIGGER reject_update BEFORE UPDATE OF zscore_threshold ON backtest_strategies
		BEGIN SELECT RAISE(ABORT, 'injected update failure'); END`)

	_, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{})
	expectStrategyChatError(t, err, http.StatusInternalServerError, StrategyChatCodeInternal)
	if status, hasResult := f.messageStatus(t, messageID); status != "pending" || hasResult {
		t.Fatalf("expected the proposal still pending without a result, got %q (result=%v)", status, hasResult)
	}
	if f.count(t, "strategy_version_history") != 0 {
		t.Fatal("expected the version snapshot rolled back")
	}
	if stored, _ := f.strategies.GetStrategy(f.strategyID); stored.ZscoreThreshold != 1.5 {
		t.Fatalf("expected the strategy unchanged, got zscore %v", stored.ZscoreThreshold)
	}

	f.exec(t, `DROP TRIGGER reject_update`)
	result, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{})
	if err != nil || result.Strategy.ZscoreThreshold != 2.0 {
		t.Fatalf("expected the retry to apply, got %+v %v", result, err)
	}
	if status, hasResult := f.messageStatus(t, messageID); status != "applied" || !hasResult {
		t.Fatalf("expected applied with a result, got %q (result=%v)", status, hasResult)
	}
}

// A failing result write rolls back the strategy change and the claim too.
func TestStrategyChatResultWriteFailureChangesNothing(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	messageID := turn.Messages[1].ID
	f.exec(t, `CREATE TRIGGER reject_result BEFORE UPDATE OF proposal_result ON strategy_chat_messages
		WHEN NEW.proposal_result IS NOT NULL
		BEGIN SELECT RAISE(ABORT, 'injected result failure'); END`)

	_, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatApplyInput{})
	expectStrategyChatError(t, err, http.StatusInternalServerError, StrategyChatCodeInternal)
	if status, hasResult := f.messageStatus(t, messageID); status != "pending" || hasResult {
		t.Fatalf("expected the proposal still pending, got %q (result=%v)", status, hasResult)
	}
	stored, _ := f.strategies.GetStrategy(f.strategyID)
	if stored.ZscoreThreshold != 1.5 || f.count(t, "strategy_version_history") != 0 {
		t.Fatalf("expected nothing changed, got zscore %v and %d snapshots", stored.ZscoreThreshold, f.count(t, "strategy_version_history"))
	}

	_, err = f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatCreateInput{Name: "Copy"})
	expectStrategyChatError(t, err, http.StatusInternalServerError, StrategyChatCodeInternal)
	if f.count(t, "backtest_strategies") != 1 {
		t.Fatal("expected the new strategy rolled back with the failed result write")
	}
	if status, _ := f.messageStatus(t, messageID); status != "pending" {
		t.Fatalf("expected the proposal still pending after the failed create, got %q", status)
	}
}

// The quota is counted inside the transaction, after the user row is claimed,
// so a strategy that another request inserts in the meantime (here a trigger
// on the claim) is counted.
func TestStrategyChatCreateStrategyCountsQuotaInsideTheTransaction(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	messageID := turn.Messages[1].ID
	f.exec(t, `UPDATE users SET max_strategies = 2 WHERE id = 1`)
	columns := `user_id, name, description, category, is_public, is_default, runtime_strategy, runtime_network, runtime_subaccount,
		pair_selection_mode, selected_markets, zscore_threshold, stats_window, max_half_life, usd_per_trade, usd_min_collateral,
		close_at_zscore_cross, find_cointegrated_pairs, manage_exits, place_trades, abort_all_positions, max_positions,
		max_drawdown_pct, stop_loss_pct, take_profit_pct, trailing_stop_pct, rebalance_interval_hours, position_timeout_hours,
		transaction_fee, slippage, starting_balance, candle_resolution, max_history_days, benchmark_symbol, risk_free_rate,
		initial_amount, usage_count, created_at, updated_at`
	f.exec(t, fmt.Sprintf(`CREATE TRIGGER quota_race AFTER UPDATE OF proposal_status ON strategy_chat_messages
		WHEN NEW.proposal_status = 'created'
		BEGIN INSERT INTO backtest_strategies (%s) SELECT %s FROM backtest_strategies WHERE id = %d; END`,
		columns, strings.Replace(columns, "name,", "'raced copy',", 1), f.strategyID))

	_, err := f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatCreateInput{Name: "Copy"})
	expectStrategyChatError(t, err, http.StatusTooManyRequests, StrategyChatCodeQuotaExceeded)
	if f.count(t, "backtest_strategies") != 1 {
		t.Fatalf("expected no strategy kept over quota, got %d", f.count(t, "backtest_strategies"))
	}
	if status, _ := f.messageStatus(t, messageID); status != "pending" {
		t.Fatalf("expected the proposal still pending, got %q", status)
	}

	// The lookup of the limit fails closed instead of assuming a default.
	f.exec(t, `DROP TRIGGER quota_race`)
	f.exec(t, `DELETE FROM users WHERE id = 1`)
	_, err = f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, messageID, StrategyChatCreateInput{Name: "Copy"})
	expectStrategyChatError(t, err, http.StatusInternalServerError, StrategyChatCodeInternal)
	if f.count(t, "backtest_strategies") != 1 {
		t.Fatal("expected no strategy created when the quota cannot be read")
	}
}

// A create whose selected changes all match the source reports applied_fields
// [] and the skipped fields, and the empty list survives the database.
func TestStrategyChatCreateStrategyReportsUnchangedFields(t *testing.T) {
	f := newStrategyChatFixture(t)
	first := f.sendTurn(t)
	second := f.sendTurn(t)
	if _, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, first.Messages[1].ID, StrategyChatApplyInput{}); err != nil {
		t.Fatalf("ApplyProposal: %v", err)
	}

	result, err := f.service.CreateStrategyFromProposal(StrategyChatActor{UserID: 1}, f.strategyID, second.Messages[1].ID, StrategyChatCreateInput{Name: "Same values"})
	if err != nil {
		t.Fatalf("CreateStrategyFromProposal: %v", err)
	}
	if result.Strategy.ZscoreThreshold != 2.0 {
		t.Fatalf("expected the copy to carry the source's current value, got %v", result.Strategy.ZscoreThreshold)
	}
	stored := result.Message.ProposalResult
	if stored == nil || stored.AppliedFields == nil || len(*stored.AppliedFields) != 0 ||
		stored.UnchangedFields == nil || len(*stored.UnchangedFields) != 1 || (*stored.UnchangedFields)[0] != "zscore_threshold" {
		t.Fatalf("expected applied_fields [] and unchanged_fields [zscore_threshold], got %+v", stored)
	}
	message, _ := f.service.repo.GetMessage(second.Messages[1].ID)
	if !strings.Contains(message.ProposalResult.String, `"applied_fields":[]`) || !strings.Contains(message.ProposalResult.String, `"unchanged_fields":["zscore_threshold"]`) {
		t.Fatalf("expected the empty list stored as [], got %s", message.ProposalResult.String)
	}
	reloaded := strategyChatMessageView(message)
	if reloaded.ProposalResult == nil || reloaded.ProposalResult.AppliedFields == nil || len(*reloaded.ProposalResult.AppliedFields) != 0 {
		t.Fatalf("expected applied_fields [] after reading the row back, got %+v", reloaded.ProposalResult)
	}
	encoded, _ := json.Marshal(reloaded)
	if !strings.Contains(string(encoded), `"applied_fields":[]`) {
		t.Fatalf("expected applied_fields [] in the API view, got %s", encoded)
	}

	// A dismissed proposal has neither list.
	third := f.sendTurn(t)
	dismissed, err := f.service.DismissProposal(StrategyChatActor{UserID: 1}, f.strategyID, third.Messages[1].ID)
	if err != nil || dismissed.ProposalResult == nil || dismissed.ProposalResult.AppliedFields != nil || dismissed.ProposalResult.UnchangedFields != nil {
		t.Fatalf("expected no field lists on a dismissed proposal, got %+v %v", dismissed, err)
	}
}

// Apply reports the row id of the snapshot, which the revert endpoint matches
// on, not its version number.
func TestStrategyChatApplyReportsTheVersionRowID(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	f.exec(t, `INSERT INTO strategy_version_history (strategy_id, version_number, config_snapshot, created_at) VALUES (999, 1, '{}', ?)`, time.Now().UTC())

	result, err := f.service.ApplyProposal(StrategyChatActor{UserID: 1}, f.strategyID, turn.Messages[1].ID, StrategyChatApplyInput{})
	if err != nil {
		t.Fatalf("ApplyProposal: %v", err)
	}
	history, err := f.strategies.GetVersionHistory(f.strategyID)
	if err != nil || len(history) != 1 {
		t.Fatalf("expected one snapshot of this strategy, got %+v %v", history, err)
	}
	versionID := result.Message.ProposalResult.VersionID
	if versionID == nil || history[0].ID != *versionID || history[0].Version == *versionID {
		t.Fatalf("expected version_id %d (row id) to differ from version_number %d, got %v", history[0].ID, history[0].Version, versionID)
	}
	var restored models.BacktestStrategy
	if err := restored.FromJSON([]byte(history[0].StrategyData.String)); err != nil || restored.ZscoreThreshold != 1.5 {
		t.Fatalf("expected the before-state in the snapshot, got %+v %v", restored, err)
	}
}

// Session and message ids of another user, another strategy or an archived
// session are not found, whoever the caller is.
func TestStrategyChatForeignSessionAndMessageIDsAreNotFound(t *testing.T) {
	f := newStrategyChatFixture(t)
	turn := f.sendTurn(t)
	sessionID := turn.Session.ID
	messageID := turn.Messages[1].ID
	other, err := f.strategies.CreateStrategy(2, "Other owner", "", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	sibling, err := f.strategies.CreateStrategy(1, "Sibling", "", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	owner := StrategyChatActor{UserID: 1}
	stranger := StrategyChatActor{UserID: 2}
	admin := StrategyChatActor{UserID: 2, IsAdmin: true}
	calls := len(f.ai.requests)

	_, err = f.service.SendMessage(context.Background(), stranger, other.ID, StrategyChatSendInput{SessionID: &sessionID, Content: "repeat the earlier conversation"})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
	_, err = f.service.SendMessage(context.Background(), owner, sibling.ID, StrategyChatSendInput{SessionID: &sessionID, Content: "hi"})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
	if _, err := f.service.StartSession(owner, f.strategyID); err != nil {
		t.Fatalf("StartSession: %v", err)
	}
	_, err = f.service.SendMessage(context.Background(), owner, f.strategyID, StrategyChatSendInput{SessionID: &sessionID, Content: "hi"})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
	if len(f.ai.requests) != calls {
		t.Fatal("expected no provider call for a refused session")
	}

	for name, strategyID := range map[string]int{"sibling strategy of the owner": sibling.ID, "another user's own strategy": other.ID} {
		actor := owner
		if strategyID == other.ID {
			actor = stranger
		}
		_, err = f.service.ApplyProposal(actor, strategyID, messageID, StrategyChatApplyInput{AcknowledgeRunning: true})
		expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
		_, err = f.service.CreateStrategyFromProposal(actor, strategyID, messageID, StrategyChatCreateInput{})
		expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
		_, err = f.service.DismissProposal(actor, strategyID, messageID)
		expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
		if status, hasResult := f.messageStatus(t, messageID); status != "pending" || hasResult {
			t.Fatalf("%s: expected the proposal untouched, got %q (result=%v)", name, status, hasResult)
		}
	}
	// An admin may read the strategy, but the owner's proposal is not theirs to act on.
	_, err = f.service.ApplyProposal(admin, f.strategyID, messageID, StrategyChatApplyInput{AcknowledgeRunning: true})
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
	_, err = f.service.DismissProposal(admin, f.strategyID, messageID)
	expectStrategyChatError(t, err, http.StatusNotFound, StrategyChatCodeNotFound)
	if status, _ := f.messageStatus(t, messageID); status != "pending" {
		t.Fatalf("expected the proposal untouched by the admin, got %q", status)
	}
	if f.count(t, "backtest_strategies") != 3 {
		t.Fatalf("expected no strategy created, got %d", f.count(t, "backtest_strategies"))
	}
}

// Apply-time revalidation enforces the risk-limit maximum and the four-fold
// rule against the strategy as it is now, even for a stored proposal.
func TestStrategyChatRevalidationEnforcesRiskLimitRules(t *testing.T) {
	strategy := chatTestStrategy() // max_drawdown 15, stop_loss 2, timeout 72
	for _, tc := range []struct {
		change StrategyChatChange
		reason string
	}{
		{StrategyChatChange{Field: "stop_loss_pct", Proposed: 9.0}, "four-fold"},
		{StrategyChatChange{Field: "max_drawdown_pct", Proposed: 61.0}, "range"},
		{StrategyChatChange{Field: "position_timeout_hours", Proposed: 721.0}, "range"},
		{StrategyChatChange{Field: "position_timeout_hours", Proposed: 289.0}, "four-fold"},
	} {
		_, _, err := revalidateStrategyChatChanges([]StrategyChatChange{tc.change}, strategy)
		var chatErr *StrategyChatError
		if !errors.As(err, &chatErr) || chatErr.Status != http.StatusBadRequest || chatErr.Code != StrategyChatCodeInvalidProposalFields || !strings.Contains(chatErr.Message, tc.reason) {
			t.Fatalf("%s -> %v: expected a 400 mentioning %q, got %v", tc.change.Field, tc.change.Proposed, tc.reason, err)
		}
	}
	updates, unchanged, err := revalidateStrategyChatChanges([]StrategyChatChange{
		{Field: "stop_loss_pct", Proposed: 8.0},
		{Field: "position_timeout_hours", Proposed: 72.0},
	}, strategy)
	if err != nil || len(updates) != 1 || len(unchanged) != 1 || unchanged[0] != "position_timeout_hours" {
		t.Fatalf("expected a four-fold change accepted and the matching one reported unchanged, got %d updates, %v, %v", len(updates), unchanged, err)
	}
}

// Provider error text is fixed per status class for users; admins also get
// the provider's own message, which can name the account or the endpoint.
func TestStrategyChatProviderErrorTextByRole(t *testing.T) {
	f := newStrategyChatFixture(t)
	owner := StrategyChatActor{UserID: 1}
	ownerAdmin := StrategyChatActor{UserID: 1, IsAdmin: true}
	const teamDetail = "AI provider returned status 404: The model grok-4.3 does not exist or your team 1b2c3d4e-team-uuid does not have access to it"
	cases := []struct {
		err      error
		expected string
	}{
		{&aiProviderCallError{StatusCode: http.StatusNotFound, Message: teamDetail}, "Grok rejected the request or the model is not available. Ask an admin to check the AI provider settings."},
		{&aiProviderCallError{StatusCode: http.StatusTooManyRequests, Message: "AI provider rate limit reached"}, "Grok rate limit reached. Try again in a minute."},
		{&aiProviderCallError{StatusCode: http.StatusBadGateway, Message: "AI provider returned status 502: upstream"}, "Grok is having trouble. Try again."},
		{&aiProviderCallError{Message: `failed to reach AI provider: Post "http://xai.internal:8443/v1/responses": dial tcp: refused`}, "Could not reach Grok. Try again."},
		{&xaiIncompleteError{Reason: "content_filter"}, "Grok could not answer. Try again."},
	}
	for _, tc := range cases {
		f.ai.err = tc.err
		_, err := f.service.SendMessage(context.Background(), owner, f.strategyID, StrategyChatSendInput{Content: "hello"})
		var chatErr *StrategyChatError
		if !errors.As(err, &chatErr) || chatErr.Status != http.StatusBadGateway || chatErr.Code != StrategyChatCodeProviderError || chatErr.Message != tc.expected {
			t.Fatalf("%v: expected %q, got %v", tc.err, tc.expected, err)
		}
		_, err = f.service.SendMessage(context.Background(), ownerAdmin, f.strategyID, StrategyChatSendInput{Content: "hello"})
		if !errors.As(err, &chatErr) || !strings.HasPrefix(chatErr.Message, tc.expected) || !strings.Contains(chatErr.Message, tc.err.Error()) {
			t.Fatalf("%v: expected the admin message to carry the provider detail, got %v", tc.err, err)
		}
	}
	if f.count(t, "strategy_chat_messages") != 0 {
		t.Fatal("expected nothing persisted after provider failures")
	}
}
