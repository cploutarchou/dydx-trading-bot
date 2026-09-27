package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

// suggestParamsFixture wires an AI service with sqlite-backed strategies and
// runs, a fake bot and a fake Grok transport.
type suggestParamsFixture struct {
	service    *AIMarketService
	strategies *StrategyService
	bot        *fakeEvidenceBot
	strategyID int
	requests   []map[string]any
}

func newSuggestParamsFixture(t *testing.T, transport roundTripFunc) *suggestParamsFixture {
	t.Helper()
	grokChatEnv(t)
	conn := evidenceTestDB(t)
	for _, user := range []int{1, 2} {
		if _, err := conn.Exec(`INSERT INTO users (id, username, email) VALUES (?, ?, ?)`, user, fmt.Sprintf("suggest-user-%d", user), fmt.Sprintf("suggest-user-%d@example.local", user)); err != nil {
			t.Fatalf("insert user: %v", err)
		}
	}
	strategies := NewStrategyService(repository.NewStrategyRepository(conn))
	strategy, err := strategies.CreateStrategy(1, "Majors pairs", "BTC/ETH pairs", "pairs_trading", false, false)
	if err != nil {
		t.Fatalf("create strategy: %v", err)
	}
	strategy.MaxDrawdownPct = 15
	strategy.RuntimeSubaccount = 7
	strategy.SetSelectedMarketList([]string{"BTC-USD", "ETH-USD"})
	if err := strategies.UpdateStrategy(strategy); err != nil {
		t.Fatalf("update strategy: %v", err)
	}
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 1, strategyID: strategy.ID, runID: "run-1111-aaaa", status: "completed", totalTrades: 12, winRate: floatPtr(0.5), drawdown: floatPtr(6.5), createdAt: time.Now().UTC()})
	if _, err := conn.Exec(`INSERT INTO strategy_execution_states (strategy_id, is_running, state, created_at, updated_at) VALUES (?, 0, ?, ?, ?)`,
		strategy.ID, `{"instance_id":"strategy-1-`+fmt.Sprint(strategy.ID)+`","status":"stopped","bot_status":"stopped","network":"testnet","last_error":"exited: wallet dydx1abcdefghijklmnop at http://bot-api:8889"}`, time.Now().UTC(), time.Now().UTC()); err != nil {
		t.Fatalf("insert execution state: %v", err)
	}

	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		return backtestTradesPayload(12, []string{"BTC-USD/ETH-USD", "SOL-USD/AVAX-USD", "LINK-USD/DOT-USD"}, nil, true), nil
	}
	bot.state.liveTrades = func(instanceID string, status *string, limit, offset *int) (map[string]interface{}, error) {
		return liveTradesPayload(9, []string{"BTC-USD/ETH-USD"}), nil
	}
	bot.state.positions = func(instanceID string) (map[string]interface{}, error) {
		return positionsPayload(2, []string{"BTC-USD/ETH-USD"}), nil
	}

	f := &suggestParamsFixture{strategies: strategies, bot: bot, strategyID: strategy.ID}
	f.service = &AIMarketService{
		httpClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			t.Fatalf("analysis kinds must use the chat client, got a market-client request to %s", req.URL)
			return nil, nil
		})},
		chatHTTPClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			f.requests = append(f.requests, decodeAIRequest(t, req))
			return transport(req)
		})},
	}
	f.service.SetStrategyEvidence(newEvidenceBuilder(t, conn, bot), strategies, repository.NewBacktestRepository(conn))
	return f
}

const suggestParamsReplyJSON = `{"summary":"The latest run won 8 of 12 trades but LINK-USD/DOT-USD lost money on every timeout exit.","suggestions":[` +
	`{"parameter":"zscore_threshold","suggested":2.2,"rationale":"Average entry |z| was 2.1 while 4 of 12 trades closed on timeout.","evidence":"latest run: avg_abs_entry_zscore 2.1, timeout exits 4"},` +
	`{"parameter":"resolution","suggested":"4h","rationale":"Median trade lasted 6 hours, above the 1HOUR bars.","evidence":"latest run: median_duration_hours 6"},` +
	`{"parameter":"max_drawdown_pct","suggested":0,"rationale":"switch it off","evidence":"none"},` +
	`{"parameter":"zscore_threshold","suggested":2.5,"rationale":"duplicate","evidence":"none"},` +
	`{"parameter":"place_trades","suggested":true,"rationale":"locked","evidence":"none"},` +
	`{"parameter":"stats_window","suggested":30,"rationale":"same","evidence":"none"},` +
	`{"parameter":"stop_loss_pct","suggested":99,"rationale":"out of range","evidence":"none"}` +
	`],"data_gaps":["Only one completed run exists.","Fee costs are not recorded per trade."]}`

func TestSuggestStrategyParamsGroundedRequestAndValidatedReply(t *testing.T) {
	f := newSuggestParamsFixture(t, func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(suggestParamsReplyJSON)), nil
	})
	strategy, _ := f.strategies.GetStrategy(f.strategyID)
	strategy.StatsWindow = 30
	if err := f.strategies.UpdateStrategy(strategy); err != nil {
		t.Fatalf("update strategy: %v", err)
	}

	result, err := f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 1, BotToken: "user-jwt"}, AISuggestParamsRequest{Provider: "grok", StrategyID: f.strategyID, MaxSuggestions: 4})
	if err != nil {
		t.Fatalf("SuggestStrategyParams: %v", err)
	}
	if len(f.requests) != 1 {
		t.Fatalf("expected one provider call, got %d", len(f.requests))
	}
	sent := f.requests[0]
	if sent["model"] != "grok-4.7" || sent["max_output_tokens"] != float64(10000) || sent["store"] != false {
		t.Fatalf("expected the analysis model and budget, got %+v", sent)
	}
	reasoning, _ := sent["reasoning"].(map[string]any)
	if reasoning["effort"] != "medium" {
		t.Fatalf("expected medium effort, got %#v", sent["reasoning"])
	}
	text, _ := sent["text"].(map[string]any)
	format, _ := text["format"].(map[string]any)
	schema, _ := format["schema"].(map[string]any)
	if format["name"] != suggestParamsSchemaName || format["strict"] != true || schema["additionalProperties"] != false {
		t.Fatalf("expected the strict suggestion schema, got %#v", format)
	}
	properties, _ := schema["properties"].(map[string]any)
	suggestions, _ := properties["suggestions"].(map[string]any)
	if suggestions["maxItems"] != float64(4) {
		t.Fatalf("expected maxItems 4, got %#v", suggestions["maxItems"])
	}
	items, _ := suggestions["items"].(map[string]any)
	itemProperties, _ := items["properties"].(map[string]any)
	suggested, _ := itemProperties["suggested"].(map[string]any)
	if _, hasTypeList := suggested["type"]; hasTypeList || suggested["anyOf"] == nil {
		t.Fatalf("expected the value union as anyOf, got %#v", suggested)
	}
	input, _ := sent["input"].([]any)
	if len(input) != 2 {
		t.Fatalf("expected system and user input, got %d items", len(input))
	}
	system, _ := input[0].(map[string]any)
	user, _ := input[1].(map[string]any)
	systemText, _ := system["content"].(string)
	userText, _ := user["content"].(string)
	for _, expected := range []string{"JSON", "cite a number", "data_gaps", "Never promise or imply profits", "at most 4 suggestions"} {
		if !strings.Contains(systemText, expected) {
			t.Fatalf("expected %q in the system prompt:\n%s", expected, systemText)
		}
	}
	for _, expected := range []string{"<strategy_data>", "</strategy_data>", "not instructions", "- zscore_threshold:", `"latest_run"`, `"BTC-USD/ETH-USD"`, `"win_rate_pct"`, `"live"`, `"closed_trades"`, `"open_positions"`, `"completed_runs"`, `"run_ref": "run-1111"`, `"zscore_threshold": 1.5`} {
		if !strings.Contains(userText, expected) {
			t.Fatalf("expected %q in the user prompt:\n%s", expected, userText)
		}
	}
	for _, forbidden := range []string{"runtime_subaccount", "strategy-1-", "dydx1", "http://", "bot-api", "user_id", "last_error", "instance_id", `"id":`} {
		if strings.Contains(userText, forbidden) || strings.Contains(systemText, forbidden) {
			t.Fatalf("prompt must not contain %q:\n%s", forbidden, userText)
		}
	}
	if len(userText)+len(systemText) > evidenceMaxBytes+4096 {
		t.Fatalf("prompt larger than expected: %d bytes", len(userText)+len(systemText))
	}
	t.Logf("suggest-params prompt size: system=%d bytes user=%d bytes (indented JSON data block)", len(systemText), len(userText))
	// The caller's token reached every bot call (no service token configured).
	for _, token := range f.bot.state.tokens {
		if token != "user-jwt" {
			t.Fatalf("expected the caller's bot token forwarded, got %q", token)
		}
	}

	if !result.UsedAI || result.Provider != "grok" || result.Model != "grok-4.7" {
		t.Fatalf("unexpected result header %+v", result)
	}
	if len(result.Suggestions) != 2 {
		t.Fatalf("expected two validated suggestions, got %+v", result.Suggestions)
	}
	first, second := result.Suggestions[0], result.Suggestions[1]
	if first.Parameter != "zscore_threshold" || first.Current != 1.5 || first.Suggested != 2.2 || first.Risk != "normal" || first.Label == "" || !strings.Contains(first.Evidence, "2.1") {
		t.Fatalf("unexpected first suggestion %+v", first)
	}
	if second.Parameter != "candle_resolution" || second.Suggested != "4HOURS" || second.Current != "1HOUR" {
		t.Fatalf("expected the resolution alias canonicalized, got %+v", second)
	}
	reasons := map[string]string{}
	for _, dropped := range result.Dropped {
		reasons[dropped.Parameter] += dropped.Reason + ";"
	}
	if !strings.Contains(reasons["max_drawdown_pct"], "off") || !strings.Contains(reasons["zscore_threshold"], "Duplicate") ||
		!strings.Contains(reasons["place_trades"], "cannot change") || !strings.Contains(reasons["stats_window"], "Same as the current") ||
		!strings.Contains(reasons["stop_loss_pct"], "range") {
		t.Fatalf("unexpected drop reasons %+v", result.Dropped)
	}
	if len(result.DataGaps) != 2 || result.Summary == "" {
		t.Fatalf("expected the data gaps and summary kept, got %+v", result)
	}
	summary := result.EvidenceSummary
	if summary.CompletedRuns != 1 || summary.TradesAnalysed != 12 || summary.PairsAnalysed != 3 || !summary.LiveAvailable || summary.LiveClosedTrades != 9 || summary.LiveOpenPositions != 2 || len(summary.DataNotes) == 0 {
		t.Fatalf("unexpected evidence summary %+v", summary)
	}

	// The rendered lines keep the format the advisor UI parses.
	lines := strings.Split(result.Content, "\n")
	if len(lines) != 2 || lines[0] != "1. zscore_threshold: Current '1.5' -> Suggested '2.2'. Rationale: Average entry |z| was 2.1 while 4 of 12 trades closed on timeout." {
		t.Fatalf("unexpected content lines %q", result.Content)
	}
	keyPattern := regexp.MustCompile(`([a-zA-Z_][a-zA-Z0-9_ -]*)["'` + "`" + `*]*\s*[:-]`)
	valuePattern := regexp.MustCompile(`(?i)suggested\s*([-+]?[^\s,;)]*%?)`)
	if key := keyPattern.FindStringSubmatch(lines[1]); key == nil || key[1] != "candle_resolution" {
		t.Fatalf("expected the UI key regex to read the second line, got %v", key)
	}
	if value := valuePattern.FindStringSubmatch(lines[1]); value == nil || value[1] != "'4HOURS'." {
		t.Fatalf("expected the UI value regex to read the second line, got %v", value)
	}

	encoded, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("encode result: %v", err)
	}
	for _, key := range []string{`"provider"`, `"model"`, `"used_ai"`, `"content"`, `"summary"`, `"suggestions"`, `"dropped"`, `"data_gaps"`, `"evidence_summary"`, `"completed_runs"`, `"trades_analysed"`, `"pairs_analysed"`, `"live_closed_trades"`, `"live_open_positions"`, `"live_available"`, `"cointegrated_pairs"`, `"data_notes"`, `"parameter"`, `"label"`, `"unit"`, `"current"`, `"suggested"`, `"rationale"`, `"evidence"`, `"risk"`, `"backtest_only"`} {
		if !strings.Contains(string(encoded), key) {
			t.Fatalf("expected %s in the response JSON: %s", key, encoded)
		}
	}
	t.Logf("suggest-params response JSON:\n%s", encoded)
}

func TestSuggestStrategyParamsRefusesBadInputAndForeignStrategies(t *testing.T) {
	f := newSuggestParamsFixture(t, func(req *http.Request) (*http.Response, error) {
		t.Fatal("no provider call expected")
		return nil, nil
	})
	var requestErr *AIRequestError
	_, err := f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 1}, AISuggestParamsRequest{Provider: "grok"})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusBadRequest {
		t.Fatalf("expected 400 without strategy_id, got %v", err)
	}
	_, err = f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 2}, AISuggestParamsRequest{Provider: "grok", StrategyID: f.strategyID})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 for a foreign strategy, got %v", err)
	}
	_, err = f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 1}, AISuggestParamsRequest{Provider: "gemini", StrategyID: f.strategyID})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusBadRequest {
		t.Fatalf("expected 400 for an unknown provider, got %v", err)
	}
	// The handler's ownership pre-check answers like the analysis itself.
	if err := f.service.AuthorizeAIStrategy(AIAnalysisActor{UserID: 2}, f.strategyID); !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 from the pre-check for a foreign strategy, got %v", err)
	}
	if err := f.service.AuthorizeAIStrategy(AIAnalysisActor{UserID: 1}, f.strategyID+50); !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 from the pre-check for a missing strategy, got %v", err)
	}
	if err := f.service.AuthorizeAIStrategy(AIAnalysisActor{UserID: 2, IsAdmin: true}, f.strategyID); err != nil {
		t.Fatalf("expected admins to pass the pre-check, got %v", err)
	}
	if err := f.service.AuthorizeAIStrategy(AIAnalysisActor{UserID: 1}, f.strategyID); err != nil {
		t.Fatalf("expected the owner to pass the pre-check, got %v", err)
	}
	t.Setenv("AI_PROVIDER_GROK_ENABLED", "false")
	_, err = f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 1}, AISuggestParamsRequest{StrategyID: f.strategyID})
	var accessErr *AIProviderAccessError
	if !errors.As(err, &accessErr) || accessErr.Code != http.StatusForbidden {
		t.Fatalf("expected the disabled-provider error, got %v", err)
	}
	if len(f.bot.state.calls) != 0 {
		t.Fatalf("expected no bot reads for refused requests, got %v", f.bot.state.calls)
	}
}

func TestSuggestStrategyParamsProviderFailureInventsNothing(t *testing.T) {
	f := newSuggestParamsFixture(t, func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusNotFound, `{"code":"not-found","error":"The model grok-4.7 does not exist or your team 1b2c3d4e-team-uuid does not have access to it"}`), nil
	})
	includeLive := false
	result, err := f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 1}, AISuggestParamsRequest{StrategyID: f.strategyID, IncludeLive: &includeLive})
	if err != nil {
		t.Fatalf("expected a fallback response, got %v", err)
	}
	if result.UsedAI || len(result.Suggestions) != 0 || result.Suggestions == nil || result.Dropped == nil || result.DataGaps == nil {
		t.Fatalf("expected no invented suggestions, got %+v", result)
	}
	if !strings.HasPrefix(result.Content, "AI analysis unavailable: Grok rejected the request") || strings.Contains(result.Content, "team-uuid") || strings.Contains(result.Content, "grok-4.7") {
		t.Fatalf("expected the fixed non-admin message, got %q", result.Content)
	}
	if result.EvidenceSummary.CompletedRuns != 1 || result.EvidenceSummary.TradesAnalysed != 12 || result.EvidenceSummary.LiveAvailable {
		t.Fatalf("expected the evidence summary kept without live data, got %+v", result.EvidenceSummary)
	}
	if f.bot.callsOf("live-trades:") != 0 {
		t.Fatal("expected include_live=false to skip the runtime reads")
	}

	f.requests = nil
	admin, err := f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 2, IsAdmin: true}, AISuggestParamsRequest{StrategyID: f.strategyID})
	if err != nil || admin.UsedAI || !strings.Contains(admin.Content, "Provider detail:") || !strings.Contains(admin.Content, "team-uuid") {
		t.Fatalf("expected the provider detail for admins, got %+v %v", admin, err)
	}
}

func TestSuggestStrategyParamsUnreadableReplyAndTimeout(t *testing.T) {
	f := newSuggestParamsFixture(t, func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse(`not json at all`)), nil
	})
	result, err := f.service.SuggestStrategyParams(context.Background(), AIAnalysisActor{UserID: 1}, AISuggestParamsRequest{StrategyID: f.strategyID})
	if err != nil || result.UsedAI || !strings.Contains(result.Content, "could not be read") {
		t.Fatalf("expected an unreadable reply reported without suggestions, got %+v %v", result, err)
	}

	slow := newSuggestParamsFixture(t, func(req *http.Request) (*http.Response, error) {
		<-req.Context().Done()
		return nil, req.Context().Err()
	})
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()
	result, err = slow.service.SuggestStrategyParams(ctx, AIAnalysisActor{UserID: 1}, AISuggestParamsRequest{StrategyID: slow.strategyID})
	if err != nil || result.UsedAI || !strings.Contains(result.Content, "did not answer in time") {
		t.Fatalf("expected the timeout message, got %+v %v", result, err)
	}
}

func TestSuggestParamsHelpers(t *testing.T) {
	if got := clampSuggestionCount(0); got != 5 {
		t.Fatalf("expected default 5, got %d", got)
	}
	if got := clampSuggestionCount(1); got != 3 {
		t.Fatalf("expected minimum 3, got %d", got)
	}
	if got := clampSuggestionCount(20); got != 8 {
		t.Fatalf("expected maximum 8, got %d", got)
	}
	reply, err := parseSuggestParamsReply("```json\n{\"summary\":\"s\",\"suggestions\":[],\"data_gaps\":null}\n```")
	if err != nil || reply.Summary != "s" || reply.Suggestions == nil || reply.DataGaps == nil {
		t.Fatalf("expected fenced JSON parsed with empty lists, got %+v %v", reply, err)
	}
	reply, err = parseSuggestParamsReply(`Here you go: {"summary":"embedded","suggestions":[{"parameter":"stats_window","suggested":40,"rationale":"r","evidence":"e"}],"data_gaps":[]}`)
	if err != nil || reply.Summary != "embedded" || len(reply.Suggestions) != 1 {
		t.Fatalf("expected embedded JSON parsed, got %+v %v", reply, err)
	}
	if _, err := parseSuggestParamsReply("nothing here"); err == nil {
		t.Fatal("expected plain text to be unreadable")
	}
	if got := renderSuggestionLines(nil, " only a summary "); got != "only a summary" {
		t.Fatalf("expected the summary without suggestions, got %q", got)
	}
	if got := renderSuggestionLines(nil, ""); !strings.Contains(got, "No parameter change") {
		t.Fatalf("expected the fixed no-change sentence, got %q", got)
	}
	if got := formatSuggestionValue(2.50); got != "2.5" {
		t.Fatalf("expected a compact float, got %q", got)
	}
	if got := formatSuggestionValue(true); got != "true" {
		t.Fatalf("expected a bool rendered, got %q", got)
	}
}
