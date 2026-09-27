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

	"github.com/dydx-trading-bot/backend-go/internal/repository"
)

type explainFixture struct {
	service  *AIMarketService
	bot      *fakeEvidenceBot
	conn     *sql.DB
	requests []map[string]any
}

func newExplainFixture(t *testing.T, transport roundTripFunc) *explainFixture {
	t.Helper()
	grokChatEnv(t)
	conn := evidenceTestDB(t)
	insertEvidenceRun(t, conn, evidenceRunRow{userID: 1, strategyID: 5, runID: "run-2222-bbbb", status: "completed", totalTrades: 12, winRate: floatPtr(0.6667), drawdown: floatPtr(4.2),
		config: `{"trading_parameters":{"zscore_threshold":2.0,"resolution":"1HOUR","runtime_subaccount":3}}`, createdAt: time.Now().UTC()})
	bot := newFakeEvidenceBot()
	bot.state.trades = func(runID string, limit, offset int) (map[string]interface{}, error) {
		return backtestTradesPayload(12, []string{"BTC-USD/ETH-USD", "SOL-USD/AVAX-USD"}, nil, true), nil
	}
	bot.state.status = func(runID string) (map[string]interface{}, error) {
		return map[string]interface{}{"success": true, "data": map[string]interface{}{"run_id": runID, "metadata": map[string]interface{}{"market_data_network": "mainnet", "drawdown_halt": map[string]interface{}{"limit_pct": 10.0, "reached": false, "trades_skipped": 0}}}}, nil
	}
	f := &explainFixture{bot: bot, conn: conn}
	f.service = &AIMarketService{
		httpClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			t.Fatalf("explanations must use the chat client, got a market-client request to %s", req.URL)
			return nil, nil
		})},
		chatHTTPClient: &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			f.requests = append(f.requests, decodeAIRequest(t, req))
			return transport(req)
		})},
	}
	f.service.SetStrategyEvidence(newEvidenceBuilder(t, conn, bot), NewStrategyService(repository.NewStrategyRepository(conn)), repository.NewBacktestRepository(conn))
	return f
}

func TestExplainBacktestByRunIDUsesTheLedger(t *testing.T) {
	f := newExplainFixture(t, func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusOK, xaiCompletedResponse("The run won 8 of 12 trades. Improvements:\n1. Raise zscore_threshold to 2.2.")), nil
	})
	result, err := f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{Provider: "grok", RunID: "run-2222-bbbb"})
	if err != nil {
		t.Fatalf("ExplainBacktest: %v", err)
	}
	if !result.UsedAI || result.Provider != "grok" || result.Model != "grok-4.7" || !strings.Contains(result.Content, "Improvements:") {
		t.Fatalf("unexpected result %+v", result)
	}
	if len(f.requests) != 1 {
		t.Fatalf("expected one provider call, got %d", len(f.requests))
	}
	sent := f.requests[0]
	if sent["model"] != "grok-4.7" || sent["max_output_tokens"] != float64(6000) {
		t.Fatalf("expected the analysis model with a 6000-token budget, got %+v", sent)
	}
	reasoning, _ := sent["reasoning"].(map[string]any)
	if reasoning["effort"] != "medium" {
		t.Fatalf("expected medium effort, got %#v", sent["reasoning"])
	}
	if _, structured := sent["text"]; structured {
		t.Fatal("expected a plain-text reply format")
	}
	input, _ := sent["input"].([]any)
	user, _ := input[1].(map[string]any)
	userText, _ := user["content"].(string)
	for _, expected := range []string{"<backtest_data>", "</backtest_data>", `"run_ref": "run-2222"`, `"win_rate_pct": 66.67`, `"max_drawdown_pct": 4.2`, `"ledger"`, `"BTC-USD/ETH-USD"`, `"exit_reasons"`, `"market_data_network": "mainnet"`, `"fees_usd"`, `"median_duration_hours"`, `"zscore_threshold": 2`, "Improvements:"} {
		if !strings.Contains(userText, expected) {
			t.Fatalf("expected %q in the prompt:\n%s", expected, userText)
		}
	}
	for _, forbidden := range []string{"runtime_subaccount", "user_id", "run-2222-bbbb", "6666.7", "420%"} {
		if strings.Contains(userText, forbidden) {
			t.Fatalf("prompt must not contain %q:\n%s", forbidden, userText)
		}
	}
	t.Logf("explain prompt size: user=%d bytes (indented JSON data block)", len(userText))
	summary := result.EvidenceSummary
	if summary.CompletedRuns != 1 || summary.TradesAnalysed != 12 || summary.PairsAnalysed != 2 || summary.LiveAvailable || summary.LiveClosedTrades != 0 || len(summary.DataNotes) == 0 {
		t.Fatalf("unexpected evidence summary %+v", summary)
	}
	encoded, _ := json.Marshal(result)
	for _, key := range []string{`"provider"`, `"model"`, `"used_ai"`, `"content"`, `"evidence_summary"`, `"data_notes"`} {
		if !strings.Contains(string(encoded), key) {
			t.Fatalf("expected %s in the response JSON: %s", key, encoded)
		}
	}
	t.Logf("explain response JSON:\n%s", encoded)
}

func TestExplainBacktestOwnershipInputAndFailures(t *testing.T) {
	f := newExplainFixture(t, func(req *http.Request) (*http.Response, error) {
		return aiJSONResponse(http.StatusServiceUnavailable, `{"error":{"message":"overloaded"}}`), nil
	})
	var requestErr *AIRequestError
	_, err := f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{Provider: "grok"})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusBadRequest {
		t.Fatalf("expected 400 without run_id, got %v", err)
	}
	_, err = f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 2}, AIBacktestExplainRequest{Provider: "grok", RunID: "run-2222-bbbb"})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 for a foreign run, got %v", err)
	}
	_, err = f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{Provider: "grok", RunID: "missing"})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 for a missing run, got %v", err)
	}
	// A run that has not completed is refused before any bot read.
	insertEvidenceRun(t, f.conn, evidenceRunRow{userID: 1, strategyID: 5, runID: "run-3333-cccc", status: "running", createdAt: time.Now().UTC()})
	_, err = f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{Provider: "grok", RunID: "run-3333-cccc"})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusConflict || requestErr.Message != "The backtest has not completed yet" {
		t.Fatalf("expected 409 for a run that has not completed, got %v", err)
	}
	if len(f.bot.state.calls) != 0 {
		t.Fatalf("expected no bot read for refused runs, got %v", f.bot.state.calls)
	}
	if len(f.requests) != 0 {
		t.Fatal("expected no provider call for refused requests")
	}
	// The handler's ownership pre-check answers like the explanation itself.
	if err := f.service.AuthorizeAIBacktestRun(context.Background(), AIAnalysisActor{UserID: 1}, "run-3333-cccc"); !errors.As(err, &requestErr) || requestErr.Status != http.StatusConflict {
		t.Fatalf("expected 409 from the pre-check for a running run, got %v", err)
	}
	if err := f.service.AuthorizeAIBacktestRun(context.Background(), AIAnalysisActor{UserID: 2}, "run-2222-bbbb"); !errors.As(err, &requestErr) || requestErr.Status != http.StatusNotFound {
		t.Fatalf("expected 404 from the pre-check for a foreign run, got %v", err)
	}
	if err := f.service.AuthorizeAIBacktestRun(context.Background(), AIAnalysisActor{UserID: 1}, " run-2222-bbbb "); err != nil {
		t.Fatalf("expected the owner's completed run (id trimmed like the explanation does) to pass the pre-check, got %v", err)
	}

	// A provider failure yields a fixed message; the admin also sees the
	// provider detail; the ledger summary is still reported.
	result, err := f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 2, IsAdmin: true}, AIBacktestExplainRequest{RunID: "run-2222-bbbb"})
	if err != nil || result.UsedAI || !strings.HasPrefix(result.Content, "AI analysis unavailable: Grok is having trouble") || !strings.Contains(result.Content, "overloaded") {
		t.Fatalf("expected the admin failure message, got %+v %v", result, err)
	}
	if len(f.requests) != 2 {
		t.Fatalf("expected the 503 retried once on the chat client, got %d calls", len(f.requests))
	}
	if result.EvidenceSummary.TradesAnalysed != 12 {
		t.Fatalf("expected the evidence summary kept, got %+v", result.EvidenceSummary)
	}
	f.requests = nil
	plain, err := f.service.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{RunID: "run-2222-bbbb"})
	if err != nil || strings.Contains(plain.Content, "overloaded") || !strings.Contains(plain.Content, "Grok is having trouble") {
		t.Fatalf("expected no provider detail for non-admins, got %+v %v", plain, err)
	}

	// Without the bot the ledger is missing but the mirror row is explained.
	orphan := &AIMarketService{chatHTTPClient: f.service.chatHTTPClient, httpClient: f.service.httpClient}
	orphan.SetStrategyEvidence(NewStrategyEvidenceBuilder(f.service.backtests, nil), f.service.strategies, f.service.backtests)
	result, err = orphan.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{RunID: "run-2222-bbbb"})
	if err != nil || result.EvidenceSummary.TradesAnalysed != 0 {
		t.Fatalf("expected a run without ledger, got %+v %v", result, err)
	}
	found := false
	for _, note := range result.EvidenceSummary.DataNotes {
		found = found || note == evidenceNoteLedgerMissing
	}
	if !found {
		t.Fatalf("expected the ledger-missing note, got %v", result.EvidenceSummary.DataNotes)
	}

	unwired := NewAIMarketService(nil)
	_, err = unwired.ExplainBacktest(context.Background(), AIAnalysisActor{UserID: 1}, AIBacktestExplainRequest{RunID: "run-2222-bbbb"})
	if !errors.As(err, &requestErr) || requestErr.Status != http.StatusServiceUnavailable {
		t.Fatalf("expected 503 from an unwired service, got %v", err)
	}
	_ = fmt.Sprint()
}
