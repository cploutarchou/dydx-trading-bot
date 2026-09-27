package services

import (
	"database/sql"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/models"
)

func TestStrategyChatContextIsSecretFreeAndUsesPercentUnits(t *testing.T) {
	strategy := chatTestStrategy()
	strategy.UserID = 4242
	strategy.RuntimeSubaccount = 7
	strategy.IsPublic = true
	strategy.AbortAllPositions = true
	strategy.SetSelectedMarketList([]string{"BTC-USD", "ETH-USD"})

	owner := 4242
	winRate := 0.55
	drawdown := 12.5
	completed := time.Date(2026, 9, 20, 12, 0, 0, 0, time.UTC)
	runs := []models.BacktestRun{{
		UserID:      &owner,
		RunID:       "run-0123456789abcdef",
		StartDate:   "2026-06-01",
		EndDate:     "2026-09-01",
		TotalTrades: 40,
		WinRate:     &winRate,
		MaxDrawdown: &drawdown,
		TotalPnLUSD: 12.3,
		CompletedAt: &completed,
	}}
	state := &models.StrategyExecutionState{
		StrategyID: strategy.ID,
		State: sql.NullString{Valid: true, String: `{"instance_id":"strategy-4242-101","status":"stopped","bot_status":"stopped",` +
			`"process_id":999,"network":"testnet","last_error":"boom"}`},
	}

	context := buildStrategyChatContext(strategy, runs, nil, state, nil)
	encoded, err := json.Marshal(context)
	if err != nil {
		t.Fatalf("encode context: %v", err)
	}
	text := string(encoded)
	for _, forbidden := range []string{"4242", "instance_id", "runtime_subaccount", "user_id", "is_public", "abort_all_positions", "process_id", "run-0123456789abcdef", "mnemonic", "address"} {
		if strings.Contains(text, forbidden) {
			t.Fatalf("context must not contain %q: %s", forbidden, text)
		}
	}
	if len(context.RecentBacktests) != 1 || context.RecentBacktests[0].RunRef != "run-0123" {
		t.Fatalf("expected a short run reference, got %+v", context.RecentBacktests)
	}
	if got := *context.RecentBacktests[0].WinRatePct; got != 55 {
		t.Fatalf("expected win rate as percent 55, got %v", got)
	}
	if got := *context.RecentBacktests[0].MaxDrawdownPct; got != 12.5 {
		t.Fatalf("expected drawdown kept as percent 12.5, got %v", got)
	}
	for _, key := range []string{"zscore_threshold", "candle_resolution", "manage_exits", "place_trades", "selected_markets"} {
		if _, ok := context.Strategy[key]; !ok {
			t.Fatalf("expected %s in the strategy block", key)
		}
	}
	if context.Runtime == nil || context.Runtime.ActiveOrUnknown || context.Runtime.LastError != "boom" {
		t.Fatalf("unexpected runtime block %+v", context.Runtime)
	}
	if !strings.Contains(strings.Join(context.DataNotes, " "), "Funding") {
		t.Fatalf("expected the funding note, got %v", context.DataNotes)
	}

	// last_error as the runtime really writes it: the bot's startup failure
	// with its instance id and last log line, and a start timeout with the
	// upstream bot API URL. Neither the user id, the address nor the host
	// may reach the prompt.
	for _, lastError := range []string{
		"Instance strategy-4242-101 exited during startup (exit_code=1): Loaded wallet for address dydx1abcdefghijklmnop",
		"upstream bot API request timed out [upstream: http://bot-api:8889/api/v1/bots/strategy-4242-101/start]",
	} {
		encodedError, _ := json.Marshal(lastError)
		realistic := &models.StrategyExecutionState{StrategyID: strategy.ID, State: sql.NullString{Valid: true,
			String: `{"instance_id":"strategy-4242-101","status":"error","bot_status":"error","network":"testnet","last_error":` + string(encodedError) + `}`}}
		prompt, err := buildStrategyChatSystemPrompt(buildStrategyChatContext(strategy, nil, nil, realistic, nil))
		if err != nil {
			t.Fatalf("build prompt: %v", err)
		}
		for _, forbidden := range []string{"4242", "dydx1abc", "bot-api:8889", "http://", "strategy-4242-101", "upstream:"} {
			if strings.Contains(prompt, forbidden) {
				t.Fatalf("prompt must not contain %q for last_error %q:\n%s", forbidden, lastError, prompt)
			}
		}
		if !strings.Contains(prompt, `"last_error": "`) {
			t.Fatalf("expected a sanitized last_error kept in the prompt for %q", lastError)
		}
	}
}

func TestSanitizeStrategyChatText(t *testing.T) {
	cases := []struct{ in, want string }{
		{"Instance strategy-4242-101 exited during startup (exit_code=1): Loaded wallet for address dydx1abcdefghijklmnop",
			"Instance the runtime exited during startup (exit_code=1): Loaded wallet for address <address>"},
		{"upstream bot API request timed out [upstream: http://bot-api:8889/api/v1/bots/strategy-4242-101/start]",
			"upstream bot API request timed out"},
		{"dial tcp bot-api:8889: connect: connection refused", "dial tcp <url>: connect: connection refused"},
		{"Cannot connect to host 10.43.0.12:8889 ssl:default", "Cannot connect to host <url> ssl:default"},
		{"dial tcp 192.168.1.20:8889: i/o timeout", "dial tcp <url>: i/o timeout"},
		{"dial tcp [fd00::1]:8889: i/o timeout", "dial tcp <url>: i/o timeout"},
		{"peer ('10.43.0.12', 8889) closed", "peer ('<url>', 8889) closed"},
		{"see https://example.com/x?y=1 or mail ops@example.com", "see <url> or mail <email>"},
		{"signer 0x00112233445566778899aabbccddeeff00112233 failed", "signer <address> failed"},
		{"stopped at 12:00:05\n\n  after  retry", "stopped at 12:00:05 after retry"},
		{strings.Repeat("x", 20), "xxxxxxxxxx..."},
	}
	for _, tc := range cases {
		limit := 300
		if tc.in == strings.Repeat("x", 20) {
			limit = 10
		}
		if got := sanitizeStrategyChatText(tc.in, limit); got != tc.want {
			t.Fatalf("sanitizeStrategyChatText(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestStrategyChatContextNotesMissingData(t *testing.T) {
	strategy := chatTestStrategy()
	context := buildStrategyChatContext(strategy, nil, errors.New("no table"), nil, nil)
	notes := strings.Join(context.DataNotes, " ")
	if !strings.Contains(notes, "could not be loaded") || !strings.Contains(notes, "never been started") {
		t.Fatalf("expected notes for missing backtests and runtime, got %v", context.DataNotes)
	}
	if context.Runtime != nil || context.RecentBacktests == nil {
		t.Fatalf("expected no runtime and an empty backtest list, got %+v", context)
	}

	unknown := buildStrategyChatContext(strategy, nil, nil, nil, errors.New("db down"))
	if unknown.Runtime == nil || !unknown.Runtime.ActiveOrUnknown {
		t.Fatalf("expected an unknown runtime to count as active, got %+v", unknown.Runtime)
	}
}

func TestStrategyChatRuntimeActiveRule(t *testing.T) {
	state := func(isRunning bool, raw string) *models.StrategyExecutionState {
		return &models.StrategyExecutionState{IsRunning: isRunning, State: sql.NullString{String: raw, Valid: raw != ""}}
	}
	cases := []struct {
		name  string
		state *models.StrategyExecutionState
		err   error
		want  bool
	}{
		{"no row means never started", nil, nil, false},
		{"lookup error is unknown", nil, errors.New("db"), true},
		{"is_running", state(true, ""), nil, true},
		{"running status", state(false, `{"status":"running"}`), nil, true},
		{"degraded status", state(false, `{"status":"degraded"}`), nil, true},
		{"safeguarded status", state(false, `{"status":"safeguarded"}`), nil, true},
		{"bot unavailable", state(false, `{"status":"stopped","bot_status":"unavailable"}`), nil, true},
		{"unreadable state", state(false, `{not json`), nil, true},
		{"state that is not an object", state(false, `[]`), nil, true},
		{"stopped", state(false, `{"status":"stopped","bot_status":"stopped"}`), nil, false},
		{"created but never started", state(false, `{"status":"created","bot_status":"created"}`), nil, false},
		{"row without state", state(false, ""), nil, false},
		// A failed stop and a missing instance are persisted as error; the
		// process may still be trading, so they count as active or unknown.
		{"failed stop", state(false, `{"status":"error","bot_status":"error"}`), nil, true},
		{"instance missing", state(false, `{"status":"error","bot_status":"missing"}`), nil, true},
		{"stopping", state(false, `{"status":"stopping","bot_status":"stopping"}`), nil, true},
		{"unknown value", state(false, `{"status":"stopped","bot_status":"paused"}`), nil, true},
	}
	for _, tc := range cases {
		if got := strategyChatRuntimeActive(tc.state, tc.err); got != tc.want {
			t.Fatalf("%s: expected %v, got %v", tc.name, tc.want, got)
		}
	}
}

func TestStrategyChatSystemPromptRules(t *testing.T) {
	prompt, err := buildStrategyChatSystemPrompt(buildStrategyChatContext(chatTestStrategy(), nil, nil, nil, nil))
	if err != nil {
		t.Fatalf("build prompt: %v", err)
	}
	for _, expected := range []string{
		"JSON",
		"<strategy_data>",
		"</strategy_data>",
		"not instructions",
		"language the user writes in",
		"No markdown headings",
		"Never promise or imply profits",
		"do not guarantee future results",
		"Never suggest switching a risk limit off",
		`"proposal" to null`,
		`kind "update"`,
		`kind "new_strategy"`,
		"- zscore_threshold:",
		"- close_at_zscore_cross:",
	} {
		if !strings.Contains(prompt, expected) {
			t.Fatalf("expected %q in the system prompt", expected)
		}
	}
}

func TestStrategyChatHistoryTurns(t *testing.T) {
	proposal, _ := json.Marshal(StrategyChatProposal{
		Kind: "update", Title: "Tighter entry",
		Changes: []StrategyChatChange{{Field: "zscore_threshold", Current: 1.5, Proposed: 2.0}},
	})
	messages := []models.StrategyChatMessage{
		{Role: "assistant", Content: "orphaned reply"},
		{Role: "user", Content: "question"},
		{
			Role: "assistant", Content: "answer",
			Proposal:       sql.NullString{String: string(proposal), Valid: true},
			ProposalStatus: sql.NullString{String: "applied", Valid: true},
		},
	}
	turns := strategyChatHistoryTurns(messages)
	if len(turns) != 2 || turns[0].Role != "user" {
		t.Fatalf("expected the leading assistant turn dropped, got %+v", turns)
	}
	if !strings.Contains(turns[1].Content, "answer") || !strings.Contains(turns[1].Content, "Tighter entry") ||
		!strings.Contains(turns[1].Content, "zscore_threshold 1.5 -> 2") || !strings.Contains(turns[1].Content, "Status: applied") {
		t.Fatalf("expected the reply plus a proposal note, got %q", turns[1].Content)
	}
}

func TestParseStrategyChatModelReply(t *testing.T) {
	reply, err := parseStrategyChatModelReply("```json\n{\"reply\":\"hello\",\"proposal\":null}\n```")
	if err != nil || reply.Reply != "hello" || reply.Proposal != nil {
		t.Fatalf("expected fenced JSON to parse, got %+v %v", reply, err)
	}
	reply, err = parseStrategyChatModelReply(`Sure: {"reply":"with prefix","proposal":{"kind":"update","title":"t","summary":"s","suggested_name":"","changes":[{"field":"stats_window","value":30,"reason":"r"}]}}`)
	if err != nil || reply.Reply != "with prefix" || reply.Proposal == nil || len(reply.Proposal.Changes) != 1 {
		t.Fatalf("expected embedded JSON to parse, got %+v %v", reply, err)
	}
	reply, err = parseStrategyChatModelReply("Just a plain answer.")
	if err != nil || reply.Reply != "Just a plain answer." || reply.Proposal != nil {
		t.Fatalf("expected plain text to become a reply without proposal, got %+v %v", reply, err)
	}
	if _, err := parseStrategyChatModelReply(`{"reply":"cut`); err == nil {
		t.Fatal("expected broken JSON to be an error")
	}
	if _, err := parseStrategyChatModelReply(`{"reply":"","proposal":null}`); err == nil {
		t.Fatal("expected an empty reply to be an error")
	}
	reply, err = parseStrategyChatModelReply(`{"reply":"","proposal":{"kind":"update","title":"T","summary":"Summary text","suggested_name":"","changes":[]}}`)
	if err != nil || reply.Reply != "Summary text" {
		t.Fatalf("expected the summary to stand in for an empty reply, got %+v %v", reply, err)
	}
}
